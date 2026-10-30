import logging
import os
from unittest.mock import Mock, mock_open, patch
import pytest
import yaml

import process_engine


@pytest.fixture(autouse=True)
def no_log_file(monkeypatch):
    """Prevent logging.basicConfig from trying to create /SCAMPI/logs/."""
    monkeypatch.setattr("logging.basicConfig", Mock())


def test_run_calls_source_extractor_and_metadata_processor(monkeypatch):
    config = {"sources": {}}
    mock_se = Mock()
    mock_mp = Mock()
    monkeypatch.setattr(process_engine.source_extractor, "source_extractor", mock_se)
    monkeypatch.setattr(process_engine.metadata_processor, "metadata_processor", mock_mp)

    with patch("builtins.open", mock_open(read_data=yaml.safe_dump(config))):
        process_engine.run()

    mock_se.assert_called_once()
    mock_mp.assert_called_once()


def test_run_raises_runtime_error_on_yaml_parse_error(monkeypatch):
    monkeypatch.setattr(process_engine.source_extractor, "source_extractor", Mock())
    monkeypatch.setattr(process_engine.metadata_processor, "metadata_processor", Mock())

    with patch("builtins.open", mock_open(read_data=":\tbad: yaml: {[")):
        with pytest.raises(RuntimeError):
            process_engine.run()

