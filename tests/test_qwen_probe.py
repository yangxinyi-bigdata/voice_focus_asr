from __future__ import annotations

import wave
from pathlib import Path

import pytest

from voice_focus_asr.qwen_probe import (
    ProbeError,
    ProbeObservation,
    WavePcm,
    _endpoint_with_model,
)


def _write_wav(path: Path, *, rate: int = 16_000, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(bytes(rate * channels * 2))


def test_wave_pcm_accepts_qwen_contract(tmp_path: Path) -> None:
    path = tmp_path / "valid.wav"
    _write_wav(path)

    audio = WavePcm.load(path)

    assert audio.duration_seconds == 1.0
    assert len(audio.chunks()) == 10
    assert all(len(chunk) == 3_200 for chunk in audio.chunks())


def test_wave_pcm_rejects_wrong_sample_rate(tmp_path: Path) -> None:
    path = tmp_path / "invalid.wav"
    _write_wav(path, rate=44_100)

    with pytest.raises(ProbeError, match="16 kHz"):
        WavePcm.load(path)


def test_observation_classifies_accepted_and_ambient_events() -> None:
    observation = ProbeObservation(
        label="mixed",
        model="test-model",
        used_voiceprint=True,
        audio_duration_seconds=2.0,
    )

    observation.observe({"type": "voiceprint_audio_list.completed"}, 100)
    observation.observe(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "目标说话人",
        },
        500,
    )
    observation.observe(
        {
            "type": "conversation.item.ambient_audio_transcription.completed",
            "transcript": "旁人",
        },
        800,
    )

    assert observation.voiceprint_status == "completed"
    assert observation.accepted_transcripts == ["目标说话人"]
    assert observation.ambient_transcripts == ["旁人"]
    assert observation.decision == "mixed"
    assert observation.milestones_ms["voiceprint_ready"] == 100


def test_observation_classifies_turn_invalid_as_rejected() -> None:
    observation = ProbeObservation(
        label="interferer",
        model="test-model",
        used_voiceprint=True,
        audio_duration_seconds=1.0,
    )
    observation.observe(
        {"type": "input_audio_buffer.speech_stopped", "reason": "turn_invalid"},
        500,
    )

    assert observation.decision == "rejected_or_ambient"


def test_observation_marks_completed_text_with_invalid_turn_as_ambiguous() -> None:
    observation = ProbeObservation(
        label="target",
        model="test-model",
        used_voiceprint=True,
        audio_duration_seconds=1.0,
    )
    observation.observe(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "目标人发言",
        },
        400,
    )
    observation.observe(
        {"type": "input_audio_buffer.speech_stopped", "reason": "turn_invalid"},
        500,
    )

    assert observation.decision == "ambiguous_accepted_with_invalid_turn"


def test_endpoint_replaces_existing_model_query() -> None:
    endpoint = "wss://example.test/realtime?region=cn&model=old"

    assert _endpoint_with_model(endpoint, "new") == (
        "wss://example.test/realtime?region=cn&model=new"
    )
