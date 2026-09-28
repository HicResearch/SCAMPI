from unittest.mock import Mock, patch, call
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
import py7zr

from source_extractor.source_extractor import _build_identifier, _cmove, source_extractor


# ── helpers ────────────────────────────────────────────────────────────────

def _status(code):
    ds = Dataset()
    ds.Status = code
    return ds


@pytest.fixture
def mock_ae(monkeypatch):
    """Patch AE in source_extractor; return (ae_class, ae_instance, assoc, server)."""
    mock_server = Mock()
    mock_assoc = Mock()
    mock_assoc.is_established = True
    mock_assoc.send_c_move.return_value = iter([(_status(0x0000), None)])

    mock_ae_instance = Mock()
    mock_ae_instance.associate.return_value = mock_assoc
    mock_ae_instance.start_server.return_value = mock_server

    mock_ae_class = Mock(return_value=mock_ae_instance)
    monkeypatch.setattr("source_extractor.source_extractor.AE", mock_ae_class)

    return mock_ae_class, mock_ae_instance, mock_assoc, mock_server


def _cmove_defaults(tmp_path, logger, **overrides):
    """Call _cmove with sensible defaults, allowing individual overrides."""
    kwargs = dict(
        aet="AET", aec="AEC", aem="AEM",
        ip="localhost", port=4242, store_port=11113,
        identifier=_build_identifier([]),
        output_dir=tmp_path, pdu=None, logger=logger,
    )
    kwargs.update(overrides)
    return _cmove(**kwargs)


# ── _build_identifier ──────────────────────────────────────────────────────

def test_build_identifier_single_key():
    ds = _build_identifier(["StudyInstanceUID=1.2.3"])
    assert ds.StudyInstanceUID == "1.2.3"


def test_build_identifier_multiple_keys():
    ds = _build_identifier(["QueryRetrieveLevel=STUDY", "PatientName=Smith"])
    assert ds.QueryRetrieveLevel == "STUDY"
    assert ds.PatientName == "Smith"


def test_build_identifier_empty_returns_empty_dataset():
    assert len(_build_identifier([])) == 0


def test_build_identifier_strips_whitespace():
    ds = _build_identifier([" StudyInstanceUID = 1.2.3 "])
    assert ds.StudyInstanceUID == "1.2.3"


def test_build_identifier_value_with_dots():
    uid = "1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6"
    ds = _build_identifier([f"StudyInstanceUID={uid}"])
    assert ds.StudyInstanceUID == uid


# ── _cmove: association ────────────────────────────────────────────────────

def test_cmove_associates_with_correct_host_port_and_aec(mock_ae, tmp_path):
    _, ae_inst, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock(), aec="ORTHANC", ip="192.168.1.1", port=104)
    ae_inst.associate.assert_called_once_with("192.168.1.1", 104, ae_title="ORTHANC")


def test_cmove_sets_ae_title(mock_ae, tmp_path):
    mock_ae_class, _, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock(), aet="LOCALMACHINE")
    mock_ae_class.assert_called_once_with(ae_title="LOCALMACHINE")


def test_cmove_sets_pdu_size_when_provided(mock_ae, tmp_path):
    _, ae_inst, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock(), pdu=16384)
    assert ae_inst.maximum_pdu_size == 16384

def test_cmove_logs_error_when_association_fails(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    assoc.is_established = False
    logger = Mock()
    _cmove_defaults(tmp_path, logger)
    logger.error.assert_called_once()
    assert "Failed to associate" in logger.error.call_args.args[0]["message"]


def test_cmove_returns_empty_list_when_association_fails(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    assoc.is_established = False
    result = _cmove_defaults(tmp_path, Mock())
    assert result == []


# ── _cmove: C-MOVE responses ───────────────────────────────────────────────

def test_cmove_sends_move_with_correct_destination(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    _cmove_defaults(tmp_path, Mock(), aem="LOCALMACHINE")
    assert assoc.send_c_move.call_args.args[1] == "LOCALMACHINE"


def test_cmove_logs_success_on_completion(mock_ae, tmp_path):
    logger = Mock()
    _cmove_defaults(tmp_path, logger)
    logger.info.assert_called_once()
    assert "C-MOVE complete" in logger.info.call_args.args[0]["message"]


def test_cmove_pending_statuses_do_not_warn(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    assoc.send_c_move.return_value = iter([
        (_status(0xFF00), None),
        (_status(0xFF01), None),
        (_status(0x0000), None),
    ])
    logger = Mock()
    _cmove_defaults(tmp_path, logger)
    logger.warning.assert_not_called()


def test_cmove_logs_warning_for_unexpected_status_code(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    assoc.send_c_move.return_value = iter([(_status(0xA801), None)])
    logger = Mock()
    _cmove_defaults(tmp_path, logger)
    logger.warning.assert_called_once()
    assert "0xA801" in logger.warning.call_args.args[0]["message"]


def test_cmove_logs_error_when_peer_aborts(mock_ae, tmp_path):
    _, _, assoc, _ = mock_ae
    assoc.send_c_move.return_value = iter([(Dataset(), None)])  # empty = abort
    logger = Mock()
    _cmove_defaults(tmp_path, logger)
    logger.error.assert_called_once()
    assert "aborted" in logger.error.call_args.args[0]["message"]


# ── _cmove: storage SCP lifecycle ─────────────────────────────────────────

def test_cmove_starts_storage_scp_on_correct_port(mock_ae, tmp_path):
    _, ae_inst, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock(), store_port=11200)
    call_args = ae_inst.start_server.call_args
    host, port = call_args.args[0]
    assert port == 11200


def test_cmove_storage_scp_is_non_blocking(mock_ae, tmp_path):
    _, ae_inst, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock())
    assert ae_inst.start_server.call_args.kwargs["block"] is False


def test_cmove_shuts_down_server_on_success(mock_ae, tmp_path):
    _, _, _, server = mock_ae
    _cmove_defaults(tmp_path, Mock())
    server.shutdown.assert_called_once()


def test_cmove_shuts_down_server_even_when_association_fails(mock_ae, tmp_path):
    _, _, assoc, server = mock_ae
    assoc.is_established = False
    _cmove_defaults(tmp_path, Mock())
    server.shutdown.assert_called_once()


def test_cmove_handle_store_saves_file_to_output_dir(mock_ae, tmp_path):
    _, ae_inst, _, _ = mock_ae
    _cmove_defaults(tmp_path, Mock())

    # Retrieve the EVT_C_STORE handler registered with start_server
    _, handler = ae_inst.start_server.call_args.kwargs["evt_handlers"][0]

    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3.4.5"
    mock_event = Mock()
    mock_event.dataset = ds
    mock_event.file_meta = FileMetaDataset()

    with patch.object(ds, "save_as") as mock_save:
        result = handler(mock_event)

    assert result == 0x0000
    mock_save.assert_called_once_with(tmp_path / "1.2.3.4.5.dcm", write_like_original=False)


def test_cmove_received_count_reflects_stored_files(mock_ae, tmp_path):
    _, ae_inst, assoc, _ = mock_ae
    logger = Mock()

    def fake_send_c_move(*args, **kwargs):
        _, handler = ae_inst.start_server.call_args.kwargs["evt_handlers"][0]
        for uid in ("1.1.1", "1.1.2", "1.1.3"):
            ds = Dataset()
            ds.SOPInstanceUID = uid
            ev = Mock()
            ev.dataset = ds
            ev.file_meta = FileMetaDataset()
            with patch.object(ds, "save_as"):
                handler(ev)
        return iter([(_status(0x0000), None)])

    assoc.send_c_move.side_effect = fake_send_c_move

    _cmove_defaults(tmp_path, logger)

    assert logger.info.call_args.args[0]["recieved"] == 3


# ── source_extractor: filesystem ──────────────────────────────────────────

def test_filesystem_source_logs_file_count(tmp_path):
    (tmp_path / "one.dcm").touch()
    (tmp_path / "two.dcm").touch()
    logger = Mock()
    config = {"sources": {"images": {"type": "filesystem", "directory": str(tmp_path)}}}

    source_extractor(config, logger)

    logger.info.assert_called_once()
    assert logger.info.call_args.args[0]["message"] == "found 2 files in images directory"


def test_missing_filesystem_directory_is_skipped(tmp_path):
    logger = Mock()
    config = {"sources": {"missing": {"type": "filesystem", "directory": str(tmp_path / "nope")}}}

    source_extractor(config, logger)

    logger.info.assert_not_called()
    logger.warning.assert_called_once()


# ── source_extractor: pacs ────────────────────────────────────────────────

@pytest.fixture
def mock_cmove(monkeypatch):
    m = Mock(return_value=[])
    monkeypatch.setattr("source_extractor.source_extractor._cmove", m)
    return m


def _pacs_config(**overrides):
    base = {
        "type": "pacs",
        "aet": "LOCALMACHINE", "aec": "ORTHANC", "aem": "LOCALMACHINE",
        "ip": "localhost", "port": 4242, "store_port": 11113,
        "keys": ["QueryRetrieveLevel=STUDY"],
    }
    base.update(overrides)
    return {"sources": {"mypacs": base}}


def test_pacs_source_calls_cmove(mock_cmove):
    source_extractor(_pacs_config(), Mock())
    mock_cmove.assert_called_once()


def test_pacs_source_passes_correct_connection_params(mock_cmove):
    source_extractor(_pacs_config(ip="10.0.0.1", port=104, aec="REMOTEPACS"), Mock())
    kw = mock_cmove.call_args.kwargs
    assert kw["ip"] == "10.0.0.1"
    assert kw["port"] == 104
    assert kw["aec"] == "REMOTEPACS"


def test_pacs_source_default_store_port(mock_cmove):
    config = {"sources": {"p": {
        "type": "pacs", "aet": "A", "aec": "B", "aem": "C",
        "ip": "localhost", "port": 4242,
        # store_port omitted
    }}}
    source_extractor(config, Mock())
    assert mock_cmove.call_args.kwargs["store_port"] == 11113


def test_pacs_source_creates_output_directory(mock_cmove, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source_extractor(_pacs_config(), Mock())
    assert (tmp_path / "received_dicoms" / "mypacs").is_dir()


def test_pacs_source_builds_identifier_from_keys(mock_cmove):
    source_extractor(_pacs_config(keys=["QueryRetrieveLevel=STUDY", "PatientName=Jones"]), Mock())
    identifier = mock_cmove.call_args.kwargs["identifier"]
    assert identifier.QueryRetrieveLevel == "STUDY"
    assert identifier.PatientName == "Jones"


def test_pacs_source_passes_pdu(mock_cmove):
    source_extractor(_pacs_config(pdu=32768), Mock())
    assert mock_cmove.call_args.kwargs["pdu"] == 32768


# ── source_extractor: filesystem – include_archives ───────────────────────

def test_filesystem_source_with_include_archives_counts_archive_files(tmp_path):
    """With include_archives, .zip and .7z files are included in the reported count."""
    (tmp_path / "scan.dcm").touch()
    (tmp_path / "backup.zip").touch()
    # (tmp_path / "compressed.7z").touch()
    (tmp_path / "readme.txt").touch()
    with py7zr.SevenZipFile( (tmp_path / "compressed.7z"), 'w') as z:
        z.write(tmp_path / "scan.dcm")
    logger = Mock()
    config = {"sources": {"images": {
        "type": "filesystem",
        "directory": str(tmp_path),
        "include_archives": True,
    }}}

    source_extractor(config, logger)

    assert logger.info.call_args.args[0]["message"] == "found 3 files in images directory"


def test_filesystem_source_without_include_archives_ignores_archive_files(tmp_path):
    """Without include_archives, .zip and .7z files are excluded from the count."""
    (tmp_path / "scan.dcm").touch()
    (tmp_path / "backup.zip").touch()
    logger = Mock()
    config = {"sources": {"images": {
        "type": "filesystem",
        "directory": str(tmp_path),
    }}}

    source_extractor(config, logger)

    assert logger.info.call_args.args[0]["message"] == "found 1 files in images directory"


# ── source_extractor: filesystem – file_regex ─────────────────────────────

def test_filesystem_source_with_file_regex_filters_matching_files(tmp_path):
    """file_regex limits the reported file count to regex-matching filenames."""
    (tmp_path / "CT_001.dcm").touch()
    (tmp_path / "CT_002.dcm").touch()
    (tmp_path / "MR_001.dcm").touch()
    logger = Mock()
    config = {"sources": {"images": {
        "type": "filesystem",
        "directory": str(tmp_path),
        "file_regex": "CT_.*",
    }}}

    source_extractor(config, logger)

    assert logger.info.call_args.args[0]["message"] == "found 2 files in images directory"


def test_filesystem_source_with_file_regex_no_match_reports_zero(tmp_path):
    """A file_regex that matches nothing yields a zero-file count."""
    (tmp_path / "CT_001.dcm").touch()
    logger = Mock()
    config = {"sources": {"images": {
        "type": "filesystem",
        "directory": str(tmp_path),
        "file_regex": "^MR_.*",
    }}}

    source_extractor(config, logger)

    assert logger.info.call_args.args[0]["message"] == "found 0 files in images directory"
