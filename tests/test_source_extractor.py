from unittest.mock import Mock

from source_extractor.source_extractor import source_extractor


def test_filesystem_source_logs_file_count(tmp_path):
    (tmp_path / "one.dcm").touch()
    (tmp_path / "two.dcm").touch()
    logger = Mock()
    config = {
        "sources": {
            "images": {"type": "filesystem", "directory": str(tmp_path)}
        }
    }

    source_extractor(config, logger)

    logger.info.assert_called_once()
    assert logger.info.call_args.args[0]["message"] == "found 2 files in images directory"


def test_missing_filesystem_source_is_skipped(tmp_path):
    logger = Mock()
    config = {
        "sources": {
            "missing": {
                "type": "filesystem",
                "directory": str(tmp_path / "does-not-exist"),
            }
        }
    }

    source_extractor(config, logger)

    # logger.warn.assert_called_once()
    logger.info.assert_not_called()


def test_pacs_source_calls_pynetdicom(monkeypatch):
    logger = Mock()
    config = {
        "sources": {
            "pacs": {
                "type": "pacs",
                "aet": "LOCALMACHINE",
                "aec": "ORTHANC",
                "aem": "LOCALMACHINE",
                "ip": "localhost",
                "port": 4242,
                "pdu": 16384,
                "store_port":11113,
                "keys":[
                     "QueryRetrieveLevel=STUDY",
                    "StudyInstanceUID=1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6"
                ]
            }
        }
    }
    source_extractor(config, logger)
    logger.error.assert_not_called()
    logger.info.assert_called_once()

def test_pacs_source_calls_pynetdicom_error(monkeypatch):
    logger = Mock()
    config = {
        "sources": {
            "pacs": {
                "type": "pacs",
                "aet": "AET",
                "aec": "AEC",
                "aem": "AEM",
                "pdu": 16384,
                "ip": "127.0.0.1",
                "port": 104,
                "store_port": 11112,
            }
        }
    }
    source_extractor(config, logger)
    logger.error.assert_called_once()
    logger.info.assert_not_called()
    

# def test_pacs_source_calls_pynetdicom_with_keys(monkeypatch):
