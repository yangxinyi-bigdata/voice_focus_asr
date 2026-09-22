from __future__ import annotations

from pathlib import Path

import pytest

from voice_focus_asr.cli import main
from voice_focus_asr.config import ConfigError, load_qwen_config


def test_load_qwen_config(tmp_path: Path) -> None:
    path = tmp_path / "config.local.toml"
    path.write_text(
        '[qwen]\napi_key = "secret"\nvoiceprint_audio_urls = '
        '["https://example.com/target.wav"]\n',
        encoding="utf-8",
    )

    config = load_qwen_config(path)

    assert config.api_key == "secret"
    assert config.voiceprint_audio_urls == ("https://example.com/target.wav",)
    assert config.model == "qwen-audio-3.1-realtime-plus"


def test_rejects_non_https_voiceprint_url(tmp_path: Path) -> None:
    path = tmp_path / "config.local.toml"
    path.write_text(
        '[qwen]\nvoiceprint_audio_urls = ["http://example.com/target.wav"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="HTTPS"):
        load_qwen_config(path)


def test_missing_config_has_actionable_message(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config.local.toml"):
        load_qwen_config(tmp_path / "config.local.toml")


def test_cli_prompts_for_key_without_printing_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "config.local.toml"
    path.write_text('[qwen]\napi_key = ""\n', encoding="utf-8")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    status = main(
        [
            "probe-qwen",
            "--config",
            str(path),
            "--audio-file",
            str(tmp_path / "unused.wav"),
            "--label",
            "test",
        ]
    )

    assert status == 2
    assert "api_key" in capsys.readouterr().err
