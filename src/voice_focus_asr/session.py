"""聚焦转写会话状态机。"""

from __future__ import annotations

import asyncio

from voice_focus_asr.contracts import AudioChunk, FocusSessionConfig, SessionState
from voice_focus_asr.errors import AudioSequenceError, InvalidSessionStateError
from voice_focus_asr.ports import StreamingRecognizer, TargetSpeakerProcessor, TranscriptHandler


class FocusedTranscriptionSession:
    """编排目标说话人处理和流式识别，但不依赖任何具体厂商。"""

    def __init__(
        self,
        *,
        config: FocusSessionConfig,
        speaker_processor: TargetSpeakerProcessor,
        recognizer: StreamingRecognizer,
        on_transcript: TranscriptHandler,
    ) -> None:
        self.config = config
        self._speaker_processor = speaker_processor
        self._recognizer = recognizer
        self._on_transcript = on_transcript
        self._state = SessionState.CREATED
        self._last_audio_sequence = -1
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SessionState:
        return self._state

    async def start(self) -> None:
        async with self._lock:
            self._require_state(SessionState.CREATED)
            self._state = SessionState.STARTING
            try:
                await self._speaker_processor.start(self.config)
                await self._recognizer.start(self.config, self._on_transcript)
            except Exception:
                self._state = SessionState.FAILED
                await self._close_components()
                raise
            self._state = SessionState.RUNNING

    async def push_audio(self, chunk: AudioChunk) -> bool:
        """处理一个分片；返回 False 表示处理器将其过滤。"""

        async with self._lock:
            self._require_state(SessionState.RUNNING)
            expected_sequence = self._last_audio_sequence + 1
            if chunk.sequence != expected_sequence:
                raise AudioSequenceError(
                    f"expected audio sequence {expected_sequence}, got {chunk.sequence}"
                )
            self._last_audio_sequence = chunk.sequence
            focused_chunk = await self._speaker_processor.process(chunk)
            if focused_chunk is None:
                return False
            await self._recognizer.accept_audio(focused_chunk)
            return True

    async def finish(self) -> None:
        async with self._lock:
            if self._state is SessionState.FINISHED:
                return
            self._require_state(SessionState.RUNNING)
            self._state = SessionState.FINISHING
            try:
                await self._speaker_processor.finish()
                await self._recognizer.finish()
            except Exception:
                self._state = SessionState.FAILED
                await self._close_components()
                raise
            await self._close_components()
            self._state = SessionState.FINISHED

    async def abort(self) -> None:
        async with self._lock:
            if self._state in {SessionState.FINISHED, SessionState.ABORTED}:
                return
            await self._close_components()
            self._state = SessionState.ABORTED

    def _require_state(self, expected: SessionState) -> None:
        if self._state is not expected:
            raise InvalidSessionStateError(
                f"operation requires state={expected}, current state={self._state}"
            )

    async def _close_components(self) -> None:
        try:
            await self._recognizer.close()
        finally:
            await self._speaker_processor.close()
