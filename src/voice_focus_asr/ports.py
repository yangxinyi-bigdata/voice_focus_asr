"""模型和云服务 Adapter 必须实现的稳定端口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from voice_focus_asr.contracts import AudioChunk, FocusSessionConfig, TranscriptUpdate

TranscriptHandler = Callable[[TranscriptUpdate], Awaitable[None]]


class TargetSpeakerProcessor(Protocol):
    """根据目标声纹过滤、增强或提取输入音频。"""

    async def start(self, config: FocusSessionConfig) -> None:
        """准备目标声纹和运行期资源。"""

    async def process(self, chunk: AudioChunk) -> AudioChunk | None:
        """返回聚焦后的音频；返回 None 表示该分片不属于目标说话人。"""

    async def finish(self) -> None:
        """刷新处理器内部仍未输出的状态。"""

    async def close(self) -> None:
        """释放资源；必须允许重复调用。"""


class StreamingRecognizer(Protocol):
    """消费聚焦音频并发布流式转写。"""

    async def start(
        self,
        config: FocusSessionConfig,
        on_transcript: TranscriptHandler,
    ) -> None:
        """启动识别会话并注册结果回调。"""

    async def accept_audio(self, chunk: AudioChunk) -> None:
        """按序接收一个音频分片。"""

    async def finish(self) -> None:
        """提交尾部音频并等待最终文本。"""

    async def close(self) -> None:
        """释放资源；必须允许重复调用。"""
