import pytest

from voice_focus_asr.contracts import AudioChunk, FocusSessionConfig


def test_session_config_requires_enrollment_audio() -> None:
    with pytest.raises(ValueError, match="enrollment"):
        FocusSessionConfig(session_id="session-1", enrollment_audio_uris=())


def test_audio_chunk_enforces_pcm_alignment() -> None:
    with pytest.raises(ValueError, match="align"):
        AudioChunk(sequence=0, pcm_s16le=b"\x00")


def test_audio_chunk_accepts_pcm16_mono_16k() -> None:
    chunk = AudioChunk(sequence=0, pcm_s16le=b"\x00\x00")

    assert chunk.sample_rate == 16_000
    assert chunk.channels == 1
