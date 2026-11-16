"""Settings from the environment and what happens when the key is missing (no shop needed)."""

from importer.__main__ import main
from importer.config import Config


def test_the_key_is_not_in_the_printed_settings(monkeypatch):
    # Short on purpose: gitleaks reports longer random-looking values next to the word "key"
    monkeypatch.setenv("PS_WEBSERVICE_KEY", "fake")
    config = Config.from_environment()
    assert config.key == "fake"
    assert "fake" not in repr(config)


def test_without_a_key_the_import_does_not_start_and_exits_with_2(monkeypatch, tmp_path):
    monkeypatch.delenv("PS_WEBSERVICE_KEY", raising=False)
    log_file = tmp_path / "importer.log"
    assert main(["--log-file", str(log_file)]) == 2
    assert "PS_WEBSERVICE_KEY is not set" in log_file.read_text(encoding="utf-8")
