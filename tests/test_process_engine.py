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


# ── _expand_env_vars ──────────────────────────────────────────────────────

def test_expand_env_vars_replaces_string_value(monkeypatch):
    monkeypatch.setenv("STUDY_UID", "1.2.3.4.5")
    result = process_engine._expand_env_vars({"key": "${STUDY_UID}"})
    assert result == {"key": "1.2.3.4.5"}


def test_expand_env_vars_replaces_value_in_list(monkeypatch):
    monkeypatch.setenv("STUDY_UID", "1.2.3.4.5")
    result = process_engine._expand_env_vars(["QueryRetrieveLevel=STUDY", "StudyInstanceUID=${STUDY_UID}"])
    assert result == ["QueryRetrieveLevel=STUDY", "StudyInstanceUID=1.2.3.4.5"]


def test_expand_env_vars_replaces_nested_value(monkeypatch):
    monkeypatch.setenv("PACS_IP", "192.168.1.10")
    config = {"sources": {"pacs": {"ip": "${PACS_IP}", "port": 4242}}}
    result = process_engine._expand_env_vars(config)
    assert result["sources"]["pacs"]["ip"] == "192.168.1.10"


def test_expand_env_vars_leaves_unset_var_unchanged(monkeypatch):
    monkeypatch.delenv("UNSET_VAR", raising=False)
    result = process_engine._expand_env_vars({"key": "${UNSET_VAR}"})
    assert result == {"key": "${UNSET_VAR}"}


def test_expand_env_vars_leaves_non_strings_unchanged(monkeypatch):
    config = {"port": 4242, "enabled": True, "ratio": 1.5, "nothing": None}
    result = process_engine._expand_env_vars(config)
    assert result == config


def test_run_expands_env_vars_before_pipeline(monkeypatch):
    monkeypatch.setenv("STUDY_UID", "1.2.3.4.5")
    config = {
        "sources": {
            "pacs": {
                "type": "pacs",
                "keys": ["QueryRetrieveLevel=STUDY", "StudyInstanceUID=${STUDY_UID}"],
            }
        }
    }
    captured = {}
    def fake_se(cfg, _logger):
        captured["config"] = cfg
    monkeypatch.setattr(process_engine.source_extractor, "source_extractor", fake_se)
    monkeypatch.setattr(process_engine.metadata_processor, "metadata_processor", Mock())

    with patch("builtins.open", mock_open(read_data=yaml.safe_dump(config))):
        process_engine.run()

    keys = captured["config"]["sources"]["pacs"]["keys"]
    assert "StudyInstanceUID=1.2.3.4.5" in keys
