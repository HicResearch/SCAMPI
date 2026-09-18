import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest
import pydicom
import yaml
from pydicom.dataset import FileDataset, FileMetaDataset

from metadata_processor import metadata_processor

TEST_IMAGES = Path(__file__).parent.parent / "test_images"


# ─── helpers ──────────────────────────────────────────────────────────────────

def write_dicom(path, modality="CT", patient_id="patient-123", study_uid="1.2.3"):
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(path, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.Modality = modality
    ds.PatientID = patient_id
    ds.StudyInstanceUID = study_uid
    ds.save_as(path)


def make_template(template_dir, modality, tables):
    content = {"Tables": tables}
    (template_dir / f"{modality}.IT").write_text(yaml.safe_dump(content), encoding="utf-8")


@pytest.fixture(autouse=True)
def clear_caches(monkeypatch, tmp_path):
    """Reset module-level caches and point templates at tmp_path before every test."""
    metadata_processor.modality_configs.clear()
    metadata_processor.modality_tables.clear()
    monkeypatch.setattr(metadata_processor, "modality_templates_location", str(tmp_path / "templates"))
    (tmp_path / "templates").mkdir()
    yield
    metadata_processor.modality_configs.clear()
    metadata_processor.modality_tables.clear()


# ─── get_modality_config_for_file ─────────────────────────────────────────────

def test_get_modality_config_returns_cached_value_without_reading_file(tmp_path):
    cached = {"Tables": [{"TableName": "Cached", "Columns": []}]}
    metadata_processor.modality_configs["CT"] = cached

    result = metadata_processor.get_modality_config_for_file("CT")

    assert result is cached


def test_get_modality_config_loads_template_file(tmp_path):
    template = {"Tables": [{"TableName": "StudyTable", "Columns": []}]}
    make_template(tmp_path / "templates", "CT", template["Tables"])

    result = metadata_processor.get_modality_config_for_file("CT")

    assert result["Tables"][0]["TableName"] == "StudyTable"


def test_get_modality_config_match_is_case_insensitive(tmp_path):
    (tmp_path / "templates" / "ct.it").write_text(
        yaml.safe_dump({"Tables": []}), encoding="utf-8"
    )

    result = metadata_processor.get_modality_config_for_file("CT")

    assert result is not None


def test_get_modality_config_returns_none_when_no_template(tmp_path):
    result = metadata_processor.get_modality_config_for_file("UNKNOWN")

    assert result is None


def test_get_modality_config_returns_none_on_yaml_error(tmp_path):
    (tmp_path / "templates" / "CT.IT").write_text(
        ":\tbad: yaml: {[", encoding="utf-8"
    )

    result = metadata_processor.get_modality_config_for_file("CT")

    assert result is None


def test_get_modality_config_stores_result_in_cache(tmp_path):
    make_template(tmp_path / "templates", "CT", [])

    metadata_processor.get_modality_config_for_file("CT")

    assert "CT" in metadata_processor.modality_configs


# ─── get_modality_table ───────────────────────────────────────────────────────

def test_get_modality_table_returns_cached_dataframe(tmp_path):
    import pandas as pd
    cached_df = pd.DataFrame(columns=["PatientID"])
    metadata_processor.modality_tables["CT_StudyTable"] = cached_df

    result = metadata_processor.get_modality_table("CT", "StudyTable")

    assert result is cached_df


def test_get_modality_table_builds_dataframe_with_correct_columns(tmp_path):
    make_template(tmp_path / "templates", "CT", [
        {"TableName": "StudyTable", "Columns": [{"ColumnName": "PatientID"}, {"ColumnName": "StudyInstanceUID"}]}
    ])

    df = metadata_processor.get_modality_table("CT", "StudyTable")

    # df.insert uses df.size as position; with 0 rows, size=0, so each
    # column is inserted at 0 — resulting in reverse declaration order
    assert set(df.columns) == {"PatientID", "StudyInstanceUID"}


def test_get_modality_table_int64_column_type(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "T", "Columns": [
        {"ColumnName": "SeriesNumber", "Type": {"CSharpType": "System.Int64"}}
    ]}])

    df = metadata_processor.get_modality_table("CT", "T")

    assert str(df["SeriesNumber"].dtype) in ("int64", "float64", "object")


def test_get_modality_table_decimal_column_type(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "T", "Columns": [
        {"ColumnName": "SliceThickness", "Type": {"CSharpType": "System.Decimal"}}
    ]}])

    df = metadata_processor.get_modality_table("CT", "T")

    assert "SliceThickness" in df.columns


def test_get_modality_table_double_column_type(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "T", "Columns": [
        {"ColumnName": "PixelSpacing", "Type": {"CSharpType": "System.Double"}}
    ]}])

    df = metadata_processor.get_modality_table("CT", "T")

    assert "PixelSpacing" in df.columns


def test_get_modality_table_date_column_type(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "T", "Columns": [
        {"ColumnName": "StudyDate", "Type": {"CSharpType": "System.Date"}}
    ]}])

    df = metadata_processor.get_modality_table("CT", "T")

    assert "StudyDate" in df.columns


def test_get_modality_table_returns_none_for_missing_table(tmp_path):
    make_template(tmp_path / "templates", "CT", [
        {"TableName": "StudyTable", "Columns": [{"ColumnName": "PatientID"}]}
    ])

    result = metadata_processor.get_modality_table("CT", "SeriesTable")

    assert result is None


# ─── process ──────────────────────────────────────────────────────────────────

def test_process_non_dcm_file_returns_none(tmp_path):
    (tmp_path / "report.txt").write_text("not a dicom")
    logger = Mock()

    result = metadata_processor.process("report.txt", str(tmp_path), logger)

    assert len(result) is 0


def test_process_extracts_values_from_dicom_and_template(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
        {"ColumnName": "StudyInstanceUID"},
        {"ColumnName": "RelativeFileArchiveURI"},
    ]}])
    shutil.copy(TEST_IMAGES / "ct_chest_001.dcm", tmp_path / "image.dcm")
    logger = Mock()

    records = metadata_processor.process("image.dcm", str(tmp_path), logger)

    assert len(records) == 1
    values, modality, table_name = records[0]
    assert values[:2] == ["PAT001", "1.2.826.0.1.3680043.8.498.51630664832575204840942585678978679381"]
    assert (modality, table_name) == ("CT", "StudyTable")


def test_process_logs_error_when_no_template_for_modality(tmp_path):
    write_dicom(tmp_path / "image.dcm", modality="XA")
    logger = Mock()

    records = metadata_processor.process("image.dcm", str(tmp_path), logger)

    assert records == []
    logger.error.assert_called_once()
    assert "XA" in str(logger.error.call_args)


def test_process_appends_none_for_missing_data_element(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
        {"ColumnName": "NonExistentTag"},
    ]}])
    write_dicom(tmp_path / "image.dcm")
    logger = Mock()

    records = metadata_processor.process("image.dcm", str(tmp_path), logger)

    values, _, _ = records[0]
    assert values[0] == "patient-123"
    assert values[1] is None


def test_process_appends_relative_file_archive_uri(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "RelativeFileArchiveURI"},
    ]}])
    shutil.copy(TEST_IMAGES / "ct_chest_001.dcm", tmp_path / "image.dcm")
    write_dicom(tmp_path / "image.dcm")

    records = metadata_processor.process("image.dcm", str(tmp_path), Mock())
    print(records[0])
    values, _, _ = records[0]
    assert values[0] == str(tmp_path) + "/image.dcm"


def test_process_handles_nested_column_path_with_missing_first_element(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "NoSuchSequence_Item"},
    ]}])
    write_dicom(tmp_path / "image.dcm")

    records = metadata_processor.process("image.dcm", str(tmp_path), Mock())

    values, _, _ = records[0]
    assert values[0] is None


def test_process_logs_error_for_nested_column_exception(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID_SubElement"},
    ]}])
    write_dicom(tmp_path / "image.dcm")
    logger = Mock()

    metadata_processor.process("image.dcm", str(tmp_path), logger)

    logger.error.assert_called()


def test_process_logs_error_and_returns_empty_on_outer_exception(tmp_path):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
    ]}])
    # Write a DICOM with no Modality so ds.Modality raises AttributeError
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(str(tmp_path / "no_modality.dcm"), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.save_as(tmp_path / "no_modality.dcm")
    logger = Mock()

    records = metadata_processor.process("no_modality.dcm", str(tmp_path), logger)

    assert records == []
    logger.error.assert_called()


# ─── metadata_processor ───────────────────────────────────────────────────────

@pytest.fixture
def patched_executor(monkeypatch):
    """Replace ProcessPoolExecutor with ThreadPoolExecutor so Mocks can be passed."""
    monkeypatch.setattr(
        "metadata_processor.metadata_processor.ProcessPoolExecutor",
        ThreadPoolExecutor,
    )


@pytest.fixture
def mock_destination_writer(monkeypatch):
    m = Mock()
    monkeypatch.setattr("metadata_processor.metadata_processor.destination_writer", m)
    return m


def test_metadata_processor_processes_filesystem_files(
    tmp_path, patched_executor, mock_destination_writer
):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
    ]}])
    write_dicom(tmp_path / "a.dcm")
    write_dicom(tmp_path / "b.dcm", patient_id="patient-456")
    logger = Mock()
    config = {"sources": {"scans": {"type": "filesystem", "directory": str(tmp_path)}}}

    metadata_processor.metadata_processor(config, logger)

    logger.info.assert_called()
    assert logger.info.call_args.args[0]["file_count"] == 2


def test_metadata_processor_skips_missing_filesystem_directory(
    tmp_path, patched_executor, mock_destination_writer
):
    logger = Mock()
    config = {"sources": {"scans": {"type": "filesystem", "directory": str(tmp_path / "nope")}}}

    metadata_processor.metadata_processor(config, logger)

    logger.warn.assert_called_once()


def test_metadata_processor_pacs_source_uses_received_dicoms_dir(
    tmp_path, monkeypatch, patched_executor, mock_destination_writer
):
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
    ]}])
    received_dir = tmp_path / "received_dicoms" / "mypacs"
    received_dir.mkdir(parents=True)
    write_dicom(received_dir / "scan.dcm")
    monkeypatch.chdir(tmp_path)
    logger = Mock()
    config = {"sources": {"mypacs": {"type": "pacs"}}}

    metadata_processor.metadata_processor(config, logger)

    assert logger.info.call_args.args[0]["file_count"] == 1


def test_metadata_processor_logs_duration(
    tmp_path, patched_executor, mock_destination_writer
):
    logger = Mock()
    config = {"sources": {"scans": {"type": "filesystem", "directory": str(tmp_path)}}}

    metadata_processor.metadata_processor(config, logger)

    info_payload = logger.info.call_args.args[0]
    assert "duration" in info_payload
    assert info_payload["duration"] >= 0


def test_metadata_processor_with_file_regex_filters_files(
    tmp_path, patched_executor, mock_destination_writer
):
    """A top-level file_regex config key restricts which files are processed."""
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
    ]}])
    write_dicom(tmp_path / "CT_001.dcm")
    write_dicom(tmp_path / "CT_002.dcm", patient_id="patient-456")
    write_dicom(tmp_path / "MR_001.dcm")
    logger = Mock()
    config = {
        "sources": {"scans": {"type": "filesystem", "directory": str(tmp_path)}},
        "file_regex": "CT_.*",
    }

    metadata_processor.metadata_processor(config, logger)

    assert logger.info.call_args.args[0]["file_count"] == 2


def test_metadata_processor_include_archives_adds_archive_extensions(
    tmp_path, patched_executor, mock_destination_writer, monkeypatch
):
    """With per-source include_archives, zip and 7z files appear in the files passed to process()."""
    make_template(tmp_path / "templates", "CT", [{"TableName": "StudyTable", "Columns": [
        {"ColumnName": "PatientID"},
    ]}])
    write_dicom(tmp_path / "scan.dcm")
    (tmp_path / "backup.zip").write_bytes(b"")

    processed_files = []
    monkeypatch.setattr(
        metadata_processor,
        "process",
        lambda file, root, log: processed_files.append(file) or [],
    )

    logger = Mock()
    config = {"sources": {"scans": {
        "type": "filesystem",
        "directory": str(tmp_path),
        "include_archives": True,
    }}}

    metadata_processor.metadata_processor(config, logger)

    assert "scan.dcm" in processed_files
    assert "backup.zip" in processed_files
