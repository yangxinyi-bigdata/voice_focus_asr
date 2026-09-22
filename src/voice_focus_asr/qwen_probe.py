"""Qwen-Audio-Realtime 声纹过滤能力探针。

这个模块只用于验证云端的说话人增强效果，不把实验性事件协议泄漏到核心领域端口。
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import wave
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_ENDPOINT = "wss://maas.qianwenaiapi.com/api-ws/v1/realtime"
DEFAULT_MODEL = "qwen-audio-3.1-realtime-plus"
EXPECTED_SAMPLE_RATE = 16_000
EXPECTED_SAMPLE_WIDTH = 2
EXPECTED_CHANNELS = 1
CHUNK_DURATION_MS = 100
CHUNK_BYTES = 3_200


class ProbeError(RuntimeError):
    """探针输入、连接或协议错误。"""


@dataclass(frozen=True, slots=True)
class WavePcm:
    """已通过千问输入契约校验的 WAV PCM。"""

    path: Path
    pcm: bytes
    frame_count: int

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / EXPECTED_SAMPLE_RATE

    @classmethod
    def load(cls, path: Path) -> WavePcm:
        try:
            with wave.open(str(path), "rb") as source:
                channels = source.getnchannels()
                sample_width = source.getsampwidth()
                sample_rate = source.getframerate()
                compression = source.getcomptype()
                frame_count = source.getnframes()
                pcm = source.readframes(frame_count)
        except (FileNotFoundError, wave.Error) as exc:
            raise ProbeError(f"无法读取 WAV 文件：{path}: {exc}") from exc

        actual = (
            f"{sample_rate} Hz, {sample_width * 8}-bit, {channels} channel(s), "
            f"compression={compression}"
        )
        if (
            channels != EXPECTED_CHANNELS
            or sample_width != EXPECTED_SAMPLE_WIDTH
            or sample_rate != EXPECTED_SAMPLE_RATE
            or compression != "NONE"
        ):
            raise ProbeError(
                "WAV 格式不符合要求；必须是 16 kHz、16-bit、单声道、未压缩 PCM，"
                f"实际为 {actual}"
            )
        if not pcm:
            raise ProbeError("WAV 文件没有音频帧")
        return cls(path=path, pcm=pcm, frame_count=frame_count)

    def chunks(self) -> list[bytes]:
        return [
            self.pcm[offset : offset + CHUNK_BYTES]
            for offset in range(0, len(self.pcm), CHUNK_BYTES)
        ]


@dataclass(slots=True)
class ProbeObservation:
    """不保存原始音频或完整服务端报文的安全实验结果。"""

    label: str
    model: str
    used_voiceprint: bool
    audio_duration_seconds: float
    voiceprint_status: str = "not_requested"
    accepted_transcripts: list[str] = field(default_factory=list)
    ambient_transcripts: list[str] = field(default_factory=list)
    stopped_reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    event_counts: Counter[str] = field(default_factory=Counter)
    milestones_ms: dict[str, int] = field(default_factory=dict)

    def observe(self, event: dict[str, Any], elapsed_ms: int) -> None:
        event_type = str(event.get("type", "unknown"))
        self.event_counts[event_type] += 1

        milestone_by_event = {
            "session.updated": "session_updated",
            "voiceprint_audio_list.completed": "voiceprint_ready",
            "conversation.item.input_audio_transcription.delta": "first_accepted_delta",
            "conversation.item.input_audio_transcription.completed": "accepted_completed",
            "conversation.item.ambient_audio_transcription.completed": "ambient_completed",
        }
        milestone = milestone_by_event.get(event_type)
        if milestone is not None:
            self.milestones_ms.setdefault(milestone, elapsed_ms)

        if event_type == "voiceprint_audio_list.in_progress":
            self.voiceprint_status = "in_progress"
        elif event_type == "voiceprint_audio_list.completed":
            self.voiceprint_status = "completed"
        elif event_type == "voiceprint_audio_list.failed":
            self.voiceprint_status = "failed"
            self.errors.append(_safe_error_text(event, "声纹注册失败"))
        elif event_type == "conversation.item.input_audio_transcription.completed":
            text = _event_text(event)
            if text:
                self.accepted_transcripts.append(text)
        elif event_type == "conversation.item.ambient_audio_transcription.completed":
            text = _event_text(event)
            if text:
                self.ambient_transcripts.append(text)
        elif event_type == "input_audio_buffer.speech_stopped":
            reason = event.get("reason")
            if isinstance(reason, str):
                self.stopped_reasons.append(reason)
        elif event_type == "error":
            self.errors.append(_safe_error_text(event, "服务端错误"))

    @property
    def decision(self) -> str:
        accepted = bool(self.accepted_transcripts)
        ambient = bool(self.ambient_transcripts)
        invalid = "turn_invalid" in self.stopped_reasons
        if accepted and invalid:
            return "ambiguous_accepted_with_invalid_turn"
        if accepted and ambient:
            return "mixed"
        if accepted:
            return "accepted"
        if ambient or invalid:
            return "rejected_or_ambient"
        return "no_decision"

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "model": self.model,
            "used_voiceprint": self.used_voiceprint,
            "voiceprint_status": self.voiceprint_status,
            "audio_duration_seconds": round(self.audio_duration_seconds, 3),
            "decision": self.decision,
            "accepted_transcripts": self.accepted_transcripts,
            "ambient_transcripts": self.ambient_transcripts,
            "stopped_reasons": self.stopped_reasons,
            "errors": self.errors,
            "event_counts": dict(sorted(self.event_counts.items())),
            "milestones_ms": self.milestones_ms,
        }


def _event_text(event: dict[str, Any]) -> str:
    for key in ("transcript", "text"):
        value = event.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def _safe_error_text(event: dict[str, Any], fallback: str) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
        parts = [str(value) for value in (code, message) if value]
        if parts:
            return ": ".join(parts)
    message = event.get("message")
    if message:
        return str(message)
    reason = event.get("reason")
    return str(reason) if reason else fallback


def _endpoint_with_model(endpoint: str, model: str) -> str:
    parts = urlsplit(endpoint)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = model
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def _receive_event(
    socket: Any,
    observation: ProbeObservation,
    started: float,
) -> dict[str, Any]:
    raw = await socket.recv()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ProbeError("服务端返回了非对象 JSON 事件")
    observation.observe(event, round((time.monotonic() - started) * 1000))
    return event


async def _wait_until_ready(
    socket: Any,
    observation: ProbeObservation,
    started: float,
    *,
    needs_voiceprint: bool,
    timeout_seconds: float,
) -> None:
    async with asyncio.timeout(timeout_seconds):
        while True:
            event = await _receive_event(socket, observation, started)
            event_type = event.get("type")
            if event_type == "error":
                raise ProbeError(observation.errors[-1])
            if event_type == "voiceprint_audio_list.failed":
                raise ProbeError(observation.errors[-1])
            if needs_voiceprint and event_type == "voiceprint_audio_list.completed":
                return
            if not needs_voiceprint and event_type == "session.updated":
                return


async def _collect_after_ready(
    socket: Any,
    observation: ProbeObservation,
    started: float,
    audio_done: asyncio.Event,
    idle_timeout_seconds: float,
) -> None:
    while True:
        timeout = idle_timeout_seconds if audio_done.is_set() else 30.0
        try:
            async with asyncio.timeout(timeout):
                event = await _receive_event(socket, observation, started)
        except TimeoutError:
            if audio_done.is_set():
                return
            raise ProbeError("发送音频期间超过 30 秒未收到服务端事件") from None
        if event.get("type") == "error":
            return


async def run_qwen_probe(
    *,
    api_key: str,
    audio: WavePcm,
    voiceprint_urls: list[str],
    label: str,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    registration_timeout_seconds: float = 60.0,
    response_idle_timeout_seconds: float = 5.0,
    trailing_silence_seconds: float = 2.0,
    realtime: bool = True,
) -> ProbeObservation:
    """运行一次声纹门控实验并返回精简观察结果。"""

    if not api_key.strip():
        raise ProbeError("API Key 为空")
    if len(voiceprint_urls) > 5:
        raise ProbeError("voiceprint_audio_urls 最多允许 5 个 URL")
    if any(not url.startswith("https://") for url in voiceprint_urls):
        raise ProbeError("声纹样本必须使用可公开访问的 HTTPS URL")

    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise ProbeError("缺少 websockets；请执行 uv sync --all-extras") from exc

    observation = ProbeObservation(
        label=label,
        model=model,
        used_voiceprint=bool(voiceprint_urls),
        audio_duration_seconds=audio.duration_seconds,
        voiceprint_status="pending" if voiceprint_urls else "not_requested",
    )
    started = time.monotonic()
    url = _endpoint_with_model(endpoint, model)

    try:
        async with connect(
            url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            max_size=8 * 1024 * 1024,
        ) as socket:
            turn_detection: dict[str, Any] = {"type": "smart_turn"}
            if voiceprint_urls:
                turn_detection["voiceprint_audio_urls"] = voiceprint_urls
            await socket.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "modalities": ["text"],
                            "input_audio_format": "pcm",
                            "turn_detection": turn_detection,
                        },
                    }
                )
            )
            await _wait_until_ready(
                socket,
                observation,
                started,
                needs_voiceprint=bool(voiceprint_urls),
                timeout_seconds=registration_timeout_seconds,
            )

            audio_done = asyncio.Event()
            collector = asyncio.create_task(
                _collect_after_ready(
                    socket,
                    observation,
                    started,
                    audio_done,
                    response_idle_timeout_seconds,
                )
            )
            for chunk in audio.chunks():
                await socket.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        }
                    )
                )
                if realtime:
                    await asyncio.sleep(len(chunk) / (EXPECTED_SAMPLE_RATE * EXPECTED_SAMPLE_WIDTH))

            silence_chunks = round(trailing_silence_seconds * 1000 / CHUNK_DURATION_MS)
            silence = bytes(CHUNK_BYTES)
            for _ in range(silence_chunks):
                await socket.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(silence).decode("ascii"),
                        }
                    )
                )
                if realtime:
                    await asyncio.sleep(CHUNK_DURATION_MS / 1000)
            audio_done.set()
            await collector
    except TimeoutError as exc:
        observation.errors.append("等待服务端事件超时")
        raise ProbeError("等待服务端事件超时") from exc

    return observation
