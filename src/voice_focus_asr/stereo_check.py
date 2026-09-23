"""双领夹麦立体声录音检查。

回答两个问题：左右声道是否真的分别来自两个麦克风；用户的声音串进目标麦克风时弱多少分贝。
只依赖标准库，适合在拿到录音后立即在本机运行。
"""

from __future__ import annotations

import math
import statistics
import sys
import wave
from array import array
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

SILENCE_FLOOR_DB = -120.0


class StereoCheckError(RuntimeError):
    """录音无法读取或不符合检查前提。"""


class ChannelSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class FrameActivity(StrEnum):
    """按两声道能量差判定的每帧说话人活动。"""

    SILENT = "silent"
    TARGET = "target"
    USER = "user"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class StereoAudio:
    """去交织后的双声道样本，数值归一化到 [-1, 1]。"""

    path: Path
    sample_rate: int
    sample_width_bytes: int
    left: list[float]
    right: list[float]

    @property
    def duration_seconds(self) -> float:
        return len(self.left) / self.sample_rate

    @classmethod
    def load(cls, path: Path) -> StereoAudio:
        try:
            with wave.open(str(path), "rb") as source:
                channels = source.getnchannels()
                width = source.getsampwidth()
                rate = source.getframerate()
                raw = source.readframes(source.getnframes())
        except (FileNotFoundError, EOFError, wave.Error) as exc:
            raise StereoCheckError(
                f"无法读取 WAV 文件：{path}: {exc}。32-bit float WAV 请先用 "
                "`ffmpeg -i in.wav -c:a pcm_s24le out.wav` 转为整数 PCM"
            ) from exc
        if channels != 2:
            raise StereoCheckError(
                f"需要双声道录音，实际为 {channels} 声道；请确认接收器处于立体声模式"
            )
        if not raw:
            raise StereoCheckError("WAV 文件没有音频帧")
        samples = _decode_pcm(raw, width)
        return cls(
            path=path,
            sample_rate=rate,
            sample_width_bytes=width,
            left=samples[0::2],
            right=samples[1::2],
        )


def _decode_pcm(raw: bytes, width: int) -> list[float]:
    if width == 2:
        values = array("h")
        values.frombytes(raw)
        scale = float(1 << 15)
    elif width == 3:
        # 把 24-bit 小端样本放进 32-bit 整数的高 3 字节，符号位随之保留。
        padded = bytearray(len(raw) // 3 * 4)
        padded[1::4] = raw[0::3]
        padded[2::4] = raw[1::3]
        padded[3::4] = raw[2::3]
        values = array("i")
        values.frombytes(bytes(padded))
        scale = float(1 << 31)
    elif width == 4:
        values = array("i")
        values.frombytes(raw)
        scale = float(1 << 31)
    else:
        raise StereoCheckError(f"不支持 {width * 8}-bit PCM")
    if sys.byteorder == "big":
        values.byteswap()
    return [value / scale for value in values]


def _db(rms: float) -> float:
    return 20 * math.log10(rms) if rms > 0 else SILENCE_FLOOR_DB


def _frame_levels_db(samples: list[float], frame_size: int) -> list[float]:
    return [
        _db(math.sqrt(math.fsum(x * x for x in samples[i : i + frame_size]) / frame_size))
        for i in range(0, len(samples) - frame_size + 1, frame_size)
    ]


def _correlation(a: list[float], b: list[float]) -> float:
    mean_a = math.fsum(a) / len(a)
    mean_b = math.fsum(b) / len(b)
    cov = math.fsum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = math.fsum((x - mean_a) ** 2 for x in a)
    var_b = math.fsum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return cov / math.sqrt(var_a * var_b)


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


@dataclass(frozen=True, slots=True)
class StereoReport:
    path: Path
    sample_rate: int
    bit_depth: int
    duration_seconds: float
    target_channel: ChannelSide
    channel_correlation: float
    target_peak_dbfs: float
    user_peak_dbfs: float
    target_clipping_ratio: float
    user_clipping_ratio: float
    activity_ratio: dict[FrameActivity, float]
    user_voice_in_target_mic_db: float | None
    target_voice_in_user_mic_db: float | None
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "audio_file": str(self.path),
            "sample_rate": self.sample_rate,
            "bit_depth": self.bit_depth,
            "duration_seconds": round(self.duration_seconds, 2),
            "target_channel": self.target_channel.value,
            "channel_correlation": round(self.channel_correlation, 3),
            "peak_dbfs": {
                "target": round(self.target_peak_dbfs, 1),
                "user": round(self.user_peak_dbfs, 1),
            },
            "clipping_ratio": {
                "target": round(self.target_clipping_ratio, 5),
                "user": round(self.user_clipping_ratio, 5),
            },
            "frame_activity_ratio": {
                key.value: round(value, 3) for key, value in self.activity_ratio.items()
            },
            "crosstalk_db": {
                "user_voice_in_target_mic": self.user_voice_in_target_mic_db,
                "target_voice_in_user_mic": self.target_voice_in_user_mic_db,
            },
            "warnings": list(self.warnings),
        }


def analyze_stereo(
    audio: StereoAudio,
    *,
    target_channel: ChannelSide,
    frame_ms: int = 100,
    silence_dbfs: float = -50.0,
    dominance_db: float = 6.0,
) -> StereoReport:
    """逐帧比较两声道能量，估计串音强度并判断声道分离是否成立。

    串音以“用户说话帧中，目标声道比用户声道低多少 dB”表示；负值越大，
    用户声音进入目标麦克风越少。
    """
    if target_channel is ChannelSide.LEFT:
        target, user = audio.left, audio.right
    else:
        target, user = audio.right, audio.left
    frame_size = audio.sample_rate * frame_ms // 1000
    if len(target) < frame_size:
        raise StereoCheckError("录音短于一个分析帧")

    target_db = _frame_levels_db(target, frame_size)
    user_db = _frame_levels_db(user, frame_size)
    counts = dict.fromkeys(FrameActivity, 0)
    user_leak: list[float] = []
    target_leak: list[float] = []
    for t, u in zip(target_db, user_db, strict=True):
        if max(t, u) < silence_dbfs:
            counts[FrameActivity.SILENT] += 1
        elif t - u >= dominance_db:
            counts[FrameActivity.TARGET] += 1
            target_leak.append(u - t)
        elif u - t >= dominance_db:
            counts[FrameActivity.USER] += 1
            user_leak.append(t - u)
        else:
            counts[FrameActivity.AMBIGUOUS] += 1
    frames = len(target_db)

    correlation = _correlation(target, user)
    clip_threshold = 0.999
    target_clip = sum(1 for x in target if abs(x) >= clip_threshold) / len(target)
    user_clip = sum(1 for x in user if abs(x) >= clip_threshold) / len(user)
    target_peak = _db(max(abs(x) for x in target))
    user_peak = _db(max(abs(x) for x in user))

    warnings: list[str] = []
    if correlation > 0.95:
        warnings.append("两声道几乎相同：接收器可能处于单声道/混合模式，双麦分离不成立")
    if target_peak < -30 or user_peak < -30:
        warnings.append("某一声道峰值低于 -30 dBFS：可能麦克风未连接、静音或增益过低")
    if target_clip > 0.001 or user_clip > 0.001:
        warnings.append("存在削波：请降低发射器增益")
    if counts[FrameActivity.TARGET] == 0:
        warnings.append(
            "没有目标声道占优的帧：如果本段目标说话人开过口，请确认 --target-channel 是否选对；"
            "“用户单说”录音出现此提示属正常"
        )

    return StereoReport(
        path=audio.path,
        sample_rate=audio.sample_rate,
        bit_depth=audio.sample_width_bytes * 8,
        duration_seconds=audio.duration_seconds,
        target_channel=target_channel,
        channel_correlation=correlation,
        target_peak_dbfs=target_peak,
        user_peak_dbfs=user_peak,
        target_clipping_ratio=target_clip,
        user_clipping_ratio=user_clip,
        activity_ratio={key: value / frames for key, value in counts.items()},
        user_voice_in_target_mic_db=_median(user_leak),
        target_voice_in_user_mic_db=_median(target_leak),
        warnings=tuple(warnings),
    )
