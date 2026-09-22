"""本地诊断入口。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

from voice_focus_asr import __version__
from voice_focus_asr.config import ConfigError, load_qwen_config
from voice_focus_asr.contracts import (
    PCM_CHANNELS,
    PCM_SAMPLE_RATE,
    PCM_SAMPLE_WIDTH_BYTES,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-focus-asr")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="检查本地运行环境与音频契约")
    probe = subcommands.add_parser(
        "probe-qwen",
        help="验证 Qwen-Audio-Realtime 的目标说话人声纹过滤效果",
    )
    probe.add_argument("--audio-file", type=Path, required=True, help="16 kHz 单声道 PCM WAV")
    probe.add_argument(
        "--config",
        type=Path,
        default=Path("config.local.toml"),
        help="本地 TOML 配置；默认使用当前目录的 config.local.toml",
    )
    voiceprint_options = probe.add_mutually_exclusive_group()
    voiceprint_options.add_argument(
        "--voiceprint-url",
        action="append",
        default=None,
        help="公开可访问的目标声纹 HTTPS URL；可重复，最多 5 个；优先于配置文件",
    )
    voiceprint_options.add_argument(
        "--without-voiceprint",
        action="store_true",
        help="忽略配置文件中的声纹 URL，运行无声纹基线",
    )
    probe.add_argument("--label", required=True, help="实验场景标签")
    probe.add_argument("--output", type=Path, help="可选 JSON 报告路径")
    probe.add_argument(
        "--model",
        default=None,
    )
    probe.add_argument(
        "--endpoint",
        default=None,
    )
    probe.add_argument(
        "--fast",
        action="store_true",
        help="不按真实时间节流，仅用于协议调试，不用于延迟评测",
    )
    return parser


def _doctor() -> int:
    supported_python = sys.version_info >= (3, 12)
    config_path = Path("config.local.toml")
    try:
        config = load_qwen_config(config_path)
        config_status = "valid"
        api_key_configured = bool(os.getenv("DASHSCOPE_API_KEY") or config.api_key)
        voiceprint_url_count = len(config.voiceprint_audio_urls)
    except ConfigError:
        config_status = "missing_or_invalid"
        api_key_configured = bool(os.getenv("DASHSCOPE_API_KEY"))
        voiceprint_url_count = 0
    report = {
        "project": "voice-focus-asr",
        "version": __version__,
        "python": platform.python_version(),
        "python_supported": supported_python,
        "audio_contract": {
            "encoding": "pcm_s16le",
            "sample_rate": PCM_SAMPLE_RATE,
            "channels": PCM_CHANNELS,
            "sample_width_bytes": PCM_SAMPLE_WIDTH_BYTES,
        },
        "model_adapter": "qwen_voiceprint_probe",
        "local_config": {
            "path": str(config_path),
            "status": config_status,
            "api_key_configured": api_key_configured,
            "voiceprint_url_count": voiceprint_url_count,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if supported_python else 1


def _probe_qwen(args: argparse.Namespace) -> int:
    from voice_focus_asr.qwen_probe import ProbeError, WavePcm, run_qwen_probe

    try:
        config = load_qwen_config(args.config)
        api_key = os.getenv("DASHSCOPE_API_KEY") or config.api_key
        if not api_key:
            print(
                "错误：请在 config.local.toml 的 [qwen] api_key 中填写 API Key",
                file=sys.stderr,
            )
            return 2
        audio = WavePcm.load(args.audio_file)
        if args.without_voiceprint:
            voiceprint_urls: list[str] = []
        elif args.voiceprint_url is not None:
            voiceprint_urls = args.voiceprint_url
        else:
            voiceprint_urls = list(config.voiceprint_audio_urls)
        observation = asyncio.run(
            run_qwen_probe(
                api_key=api_key,
                audio=audio,
                voiceprint_urls=voiceprint_urls,
                label=args.label,
                model=args.model or os.getenv("VOICE_FOCUS_QWEN_MODEL") or config.model,
                endpoint=args.endpoint or os.getenv("VOICE_FOCUS_QWEN_ENDPOINT") or config.endpoint,
                realtime=not args.fast,
            )
        )
    except (ConfigError, ProbeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    report = observation.as_dict()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if observation.errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "doctor":
        return _doctor()
    if args.command == "probe-qwen":
        return _probe_qwen(args)
    return 2
