from __future__ import annotations

import asyncio

import pytest

from voice_focus_asr.contracts import (
    AudioChunk,
    FocusSessionConfig,
    SessionState,
    TranscriptUpdate,
)
from voice_focus_asr.errors import AudioSequenceError, InvalidSessionStateError
from voice_focus_asr.ports import TranscriptHandler
from voice_focus_asr.session import FocusedTranscriptionSession


class FakeSpeakerProcessor:
    def __init__(self, *, drop_sequences: set[int] | None = None) -> None:
        self.drop_sequences = drop_sequences or set()
        self.closed = False

    async def start(self, config: FocusSessionConfig) -> None:
        assert config.enrollment_audio_uris

    async def process(self, chunk: AudioChunk) -> AudioChunk | None:
        return None if chunk.sequence in self.drop_sequences else chunk

    async def finish(self) -> None:
        return None

    async def close(self) -> None:
        self.closed = True


class FakeRecognizer:
    def __init__(self) -> None:
        self.sequences: list[int] = []
        self.closed = False
        self._handler: TranscriptHandler | None = None

    async def start(
        self,
        config: FocusSessionConfig,
        on_transcript: TranscriptHandler,
    ) -> None:
        assert config.language == "zh"
        self._handler = on_transcript

    async def accept_audio(self, chunk: AudioChunk) -> None:
        self.sequences.append(chunk.sequence)
        assert self._handler is not None
        await self._handler(
            TranscriptUpdate(sequence=chunk.sequence, text=f"片段{chunk.sequence}", is_final=False)
        )

    async def finish(self) -> None:
        return None

    async def close(self) -> None:
        self.closed = True


def _config() -> FocusSessionConfig:
    return FocusSessionConfig(
        session_id="session-1",
        enrollment_audio_uris=("https://example.test/target.wav",),
    )


def test_session_filters_non_target_audio_and_finishes() -> None:
    async def scenario() -> None:
        updates: list[TranscriptUpdate] = []

        async def on_transcript(update: TranscriptUpdate) -> None:
            updates.append(update)

        processor = FakeSpeakerProcessor(drop_sequences={1})
        recognizer = FakeRecognizer()
        session = FocusedTranscriptionSession(
            config=_config(),
            speaker_processor=processor,
            recognizer=recognizer,
            on_transcript=on_transcript,
        )

        await session.start()
        assert await session.push_audio(AudioChunk(sequence=0, pcm_s16le=b"\x00\x00"))
        assert not await session.push_audio(AudioChunk(sequence=1, pcm_s16le=b"\x00\x00"))
        await session.finish()

        assert session.state is SessionState.FINISHED
        assert recognizer.sequences == [0]
        assert [update.text for update in updates] == ["片段0"]
        assert processor.closed
        assert recognizer.closed

    asyncio.run(scenario())


def test_session_rejects_audio_before_start() -> None:
    async def scenario() -> None:
        async def on_transcript(update: TranscriptUpdate) -> None:
            del update

        session = FocusedTranscriptionSession(
            config=_config(),
            speaker_processor=FakeSpeakerProcessor(),
            recognizer=FakeRecognizer(),
            on_transcript=on_transcript,
        )

        with pytest.raises(InvalidSessionStateError):
            await session.push_audio(AudioChunk(sequence=0, pcm_s16le=b"\x00\x00"))

    asyncio.run(scenario())


def test_session_rejects_out_of_order_audio() -> None:
    async def scenario() -> None:
        async def on_transcript(update: TranscriptUpdate) -> None:
            del update

        session = FocusedTranscriptionSession(
            config=_config(),
            speaker_processor=FakeSpeakerProcessor(),
            recognizer=FakeRecognizer(),
            on_transcript=on_transcript,
        )
        await session.start()

        with pytest.raises(AudioSequenceError, match="expected audio sequence 0"):
            await session.push_audio(AudioChunk(sequence=1, pcm_s16le=b"\x00\x00"))

    asyncio.run(scenario())
