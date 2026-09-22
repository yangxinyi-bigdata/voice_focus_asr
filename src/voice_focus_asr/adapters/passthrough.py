"""只用于链路测试的无过滤目标说话人处理器。"""

from voice_focus_asr.contracts import AudioChunk, FocusSessionConfig


class PassthroughSpeakerProcessor:
    """原样返回全部音频，用于建立未过滤基线。"""

    async def start(self, config: FocusSessionConfig) -> None:
        del config

    async def process(self, chunk: AudioChunk) -> AudioChunk:
        return chunk

    async def finish(self) -> None:
        return None

    async def close(self) -> None:
        return None
