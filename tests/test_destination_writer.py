from unittest.mock import Mock, patch
import pandas as pd
import pytest

from destination_writer.destination_writer import destination_writer, write_file, write_metadata


def test_write_metadata_bad_connection():
    logger = Mock()
    config = {
        "destination":{
            "metadata":{
                "dbType":"MSSQL",
                "connectionString":"",
                "index":"test"
            }
        }
    }
    table_name="test_write_metadata"
    dataframe = pd.DataFrame()
    dataframe.insert(0,"test",[1])
    destination_writer(config,logger,table_name,dataframe)
    logger.debug.assert_called_once()
    assert logger.debug.call_args.args[0]["message"] == f"Writing 1 records to {table_name}"
    logger.error.assert_called_once()


def test_write_metadata_db_not_implemented():
    logger = Mock()
    config = {
        "destination":{
            "metadata":{
                "dbType":"Junk",
                "connectionString":"",
                "index":"test"
            }
        }
    }
    table_name="test_write_metadata"
    dataframe = pd.DataFrame()
    dataframe.insert(0,"test",[1])
    destination_writer(config,logger,table_name,dataframe)
    logger.debug.assert_not_called()
    logger.info.assert_called_once()
    assert logger.info.call_args.args[0]["message"] == f"Junk not implemented"


# ── write_metadata: MSSQL success path ────────────────────────────────────

def test_write_metadata_mssql_logs_finished_on_success(monkeypatch):
    """Both 'Writing' and 'Finished writing' debug logs are emitted when to_sql succeeds."""
    monkeypatch.setattr(pd.DataFrame, "to_sql", lambda *a, **kw: None)

    logger = Mock()
    config = {
        "destination": {
            "metadata": {"dbType": "MSSQL", "connectionString": "fake_conn", "index": "id"},
        }
    }
    df = pd.DataFrame({"PatientID": ["PAT001"]})

    write_metadata(config, logger, "TestTable", df)

    assert logger.debug.call_count == 2
    messages = [c.args[0]["message"] for c in logger.debug.call_args_list]
    assert any("Finished writing" in m for m in messages)
    assert any("Writing" in m for m in messages)


# ── destination_writer: write_file routing ────────────────────────────────

def test_destination_writer_calls_write_file_when_rfau_column_present(monkeypatch):
    """destination_writer routes to write_file when RelativeFileArchiveURI is a column."""
    mock_write_file = Mock()
    mock_write_metadata = Mock()
    monkeypatch.setattr("destination_writer.destination_writer.write_file", mock_write_file)
    monkeypatch.setattr("destination_writer.destination_writer.write_metadata", mock_write_metadata)

    config = {}
    logger = Mock()
    df = pd.DataFrame({"RelativeFileArchiveURI": ["/some/path/file.dcm"]})

    destination_writer(config, logger, "SomeTable", df)

    mock_write_metadata.assert_called_once_with(config, logger, "SomeTable", df)
    mock_write_file.assert_called_once_with(config, logger, df)


# ── write_file ────────────────────────────────────────────────────────────────

def test_write_file_copies_files_to_destination(monkeypatch):
    """write_file calls shutil.copyfile for each row and logs timing/count."""
    mock_copyfile = Mock()
    mock_get_dest = Mock(return_value="/dest/file.dcm")
    monkeypatch.setattr("destination_writer.destination_writer.shutil.copyfile", mock_copyfile)
    monkeypatch.setattr("destination_writer.destination_writer.get_destination_location", mock_get_dest)

    config = {"destination": {"files": {"directory": "/dest"}}}
    logger = Mock()
    df = pd.DataFrame({"RelativeFileArchiveURI": ["/src/file.dcm"]})

    write_file(config, logger, df)

    mock_copyfile.assert_called_once_with("/src/file.dcm", "/dest/file.dcm")
    logger.info.assert_called_once()
    assert "Wrote 1 files" in logger.info.call_args.args[0]["message"]


def test_write_file_skips_copy_when_destination_is_none(monkeypatch):
    """write_file does not call shutil.copyfile when get_destination_location returns None."""
    mock_copyfile = Mock()
    monkeypatch.setattr("destination_writer.destination_writer.shutil.copyfile", mock_copyfile)
    monkeypatch.setattr(
        "destination_writer.destination_writer.get_destination_location",
        Mock(return_value=None),
    )

    config = {"destination": {"files": {"directory": "/dest"}}}
    logger = Mock()
    df = pd.DataFrame({"RelativeFileArchiveURI": ["/src/file.dcm"]})

    write_file(config, logger, df)

    mock_copyfile.assert_not_called()
    logger.info.assert_called_once()


# ── write_metadata line 27: if 'RelativeFileArchiveURI' in dataframe ──────────

def test_write_metadata_resolves_file_paths_when_rfau_column_present(monkeypatch):
    """Line 27 branch: get_destination_location is called for each row when RFAU column exists."""
    mock_get_dest = Mock(return_value="/dest/file.dcm")
    monkeypatch.setattr(
        "destination_writer.destination_writer.get_destination_location", mock_get_dest
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", lambda *a, **kw: None)

    config = {
        "destination": {
            "files": {"directory": "/dest"},
            "metadata": {"dbType": "MSSQL", "connectionString": "fake", "index": "id"},
        }
    }
    logger = Mock()
    df = pd.DataFrame({"RelativeFileArchiveURI": ["/src/file.dcm"]})

    write_metadata(config, logger, "TestTable", df)

    mock_get_dest.assert_called_once()


def test_write_metadata_skips_file_paths_when_rfau_column_absent(monkeypatch):
    """Line 27 branch: get_destination_location is not called when RFAU column is absent."""
    mock_get_dest = Mock()
    monkeypatch.setattr(
        "destination_writer.destination_writer.get_destination_location", mock_get_dest
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", lambda *a, **kw: None)

    config = {
        "destination": {
            "metadata": {"dbType": "MSSQL", "connectionString": "fake", "index": "id"},
        }
    }
    logger = Mock()
    df = pd.DataFrame({"PatientID": ["PAT001"]})

    write_metadata(config, logger, "TestTable", df)

    mock_get_dest.assert_not_called()


def test_destination_writer_does_not_call_write_file_without_rfau_column(monkeypatch):
    """destination_writer skips write_file when RelativeFileArchiveURI is not a column."""
    mock_write_file = Mock()
    monkeypatch.setattr("destination_writer.destination_writer.write_file", mock_write_file)

    config = {
        "destination": {"metadata": {"dbType": "Junk", "connectionString": "", "index": "test"}}
    }
    logger = Mock()
    df = pd.DataFrame({"PatientID": ["PAT001"]})

    destination_writer(config, logger, "SomeTable", df)

    mock_write_file.assert_not_called()
