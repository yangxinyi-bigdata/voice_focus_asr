"""跨 Adapter 保持稳定的领域数据契约。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PCM_SAMPLE_RATE = 16_000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH_BYTES = 2


class SessionState(StrEnum):
    """聚焦转写会话的生命周期状态。"""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    FINISHING = "finishing"
    FINISHED = "finished"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FocusSessionConfig:
    """一次聚焦转写会话所需的不可变配置。"""

    session_id: str
    enrollment_audio_uris: tuple[str, ...]
    language: str = "zh"
    sample_rate: int = PCM_SAMPLE_RATE

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.enrollment_audio_uris:
            raise ValueError("at least one enrollment audio URI is required")
        if any(not uri.strip() for uri in self.enrollment_audio_uris):
            raise ValueError("enrollment audio URI must not be empty")
        if not self.language.strip():
            raise ValueError("language must not be empty")
        if self.sample_rate != PCM_SAMPLE_RATE:
            raise ValueError(f"sample_rate must be {PCM_SAMPLE_RATE}")


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """按严格顺序进入聚焦转写链路的 PCM 音频分片。"""

    sequence: int
    pcm_s16le: bytes
    sample_rate: int = PCM_SAMPLE_RATE
    channels: int = PCM_CHANNELS
    sample_width_bytes: int = PCM_SAMPLE_WIDTH_BYTES

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.pcm_s16le:
            raise ValueError("audio chunk must not be empty")
        if len(self.pcm_s16le) % self.sample_width_bytes:
            raise ValueError("PCM byte length must align to the sample width")
        if self.sample_rate != PCM_SAMPLE_RATE:
            raise ValueError(f"sample_rate must be {PCM_SAMPLE_RATE}")
        if self.channels != PCM_CHANNELS:
            raise ValueError(f"channels must be {PCM_CHANNELS}")
        if self.sample_width_bytes != PCM_SAMPLE_WIDTH_BYTES:
            raise ValueError(f"sample_width_bytes must be {PCM_SAMPLE_WIDTH_BYTES}")


@dataclass(frozen=True, slots=True)
class TranscriptUpdate:
    """识别器发布给上层的增量或最终文本。"""

    sequence: int
    text: str
    is_final: bool
    speaker_label: str = "target"

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.text:
            raise ValueError("transcript text must not be empty")
        if not self.speaker_label.strip():
            raise ValueError("speaker_label must not be empty")
