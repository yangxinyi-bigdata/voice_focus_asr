from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from voice_focus_asr.stereo_check import (
    ChannelSide,
    FrameActivity,
    StereoAudio,
    StereoCheckError,
    analyze_stereo,
)

RATE = 16_000


def _tone(seconds: float, amplitude: float, freq: float) -> list[float]:
    return [
        amplitude * math.sin(2 * math.pi * freq * i / RATE) for i in range(int(seconds * RATE))
    ]


def _write(path: Path, left: list[float], right: list[float], *, width: int = 2) -> None:
    frames = bytearray()
    for sample_l, sample_r in zip(left, right, strict=True):
        for value in (sample_l, sample_r):
            if width == 2:
                frames += struct.pack("<h", round(value * 32767))
            else:
                frames += round(value * 8_388_607).to_bytes(3, "little", signed=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(width)
        output.setframerate(RATE)
        output.writeframes(bytes(frames))


def _conversation(tmp_path: Path, *, width: int = 2) -> Path:
    """左声道=目标：先目标说 1 秒（右声道串音 -20 dB），再用户说 1 秒（左声道串音 -14 dB）。"""
    target_speaks = _tone(1.0, 0.3, 220)
    user_speaks = _tone(1.0, 0.3, 330)
    left = target_speaks + [x * 10 ** (-14 / 20) for x in user_speaks]
    right = [x * 0.1 for x in target_speaks] + user_speaks
    path = tmp_path / "conversation.wav"
    _write(path, left, right, width=width)
    return path


@pytest.mark.parametrize("width", [2, 3])
def test_estimates_crosstalk_per_direction(tmp_path: Path, width: int) -> None:
    audio = StereoAudio.load(_conversation(tmp_path, width=width))

    report = analyze_stereo(audio, target_channel=ChannelSide.LEFT)

    assert report.bit_depth == width * 8
    assert report.activity_ratio[FrameActivity.TARGET] == pytest.approx(0.5)
    assert report.activity_ratio[FrameActivity.USER] == pytest.approx(0.5)
    assert report.target_voice_in_user_mic_db == pytest.approx(-20.0, abs=0.2)
    assert report.user_voice_in_target_mic_db == pytest.approx(-14.0, abs=0.2)
    assert report.warnings == ()


def test_swapped_target_channel_swaps_roles(tmp_path: Path) -> None:
    audio = StereoAudio.load(_conversation(tmp_path))

    report = analyze_stereo(audio, target_channel=ChannelSide.RIGHT)

    assert report.user_voice_in_target_mic_db == pytest.approx(-20.0, abs=0.2)


def test_warns_when_channels_are_duplicated(tmp_path: Path) -> None:
    mono = _tone(1.0, 0.3, 220)
    path = tmp_path / "dup.wav"
    _write(path, mono, mono)

    report = analyze_stereo(StereoAudio.load(path), target_channel=ChannelSide.LEFT)

    assert report.channel_correlation == pytest.approx(1.0)
    assert any("几乎相同" in warning for warning in report.warnings)


def test_rejects_mono_recording(tmp_path: Path) -> None:
    path = tmp_path / "mono.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(bytes(RATE * 2))

    with pytest.raises(StereoCheckError, match="双声道"):
        StereoAudio.load(path)
