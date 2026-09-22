"""对外稳定的领域异常。"""


class VoiceFocusError(RuntimeError):
    """Voice Focus ASR 的基础异常。"""


class InvalidSessionStateError(VoiceFocusError):
    """调用与当前会话状态不兼容。"""


class AudioSequenceError(VoiceFocusError):
    """音频分片序号缺失、重复或乱序。"""
