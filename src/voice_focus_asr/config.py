"""读取实验用本地配置；密钥不进入仓库或日志。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_MODEL = "qwen-audio-3.1-realtime-plus"
DEFAULT_ENDPOINT = "wss://maas.qianwenaiapi.com/api-ws/v1/realtime"


class ConfigError(ValueError):
    """本地配置缺失或格式无效。"""


@dataclass(frozen=True, slots=True)
class QwenConfig:
    api_key: str
    model: str
    endpoint: str
    voiceprint_audio_urls: tuple[str, ...]


def load_qwen_config(path: Path) -> QwenConfig:
    """从 TOML 文件读取千问探针配置，不读取或输出其他配置节。"""

    try:
        with path.open("rb") as source:
            document = tomllib.load(source)
    except FileNotFoundError as exc:
        raise ConfigError(
            f"找不到配置文件 {path}；请在项目根目录创建 config.local.toml"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置文件 TOML 格式无效：{path}: {exc}") from exc

    qwen = document.get("qwen")
    if not isinstance(qwen, dict):
        raise ConfigError("配置文件缺少 [qwen] 节")

    api_key = _string_field(qwen, "api_key", "")
    model = _string_field(qwen, "model", DEFAULT_MODEL)
    endpoint = _string_field(qwen, "endpoint", DEFAULT_ENDPOINT)
    urls = qwen.get("voiceprint_audio_urls", [])
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        raise ConfigError("qwen.voiceprint_audio_urls 必须是字符串数组")
    if len(urls) > 5:
        raise ConfigError("qwen.voiceprint_audio_urls 最多允许 5 个 URL")
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ConfigError("qwen.voiceprint_audio_urls 只能包含完整的 HTTPS URL")

    parsed_endpoint = urlsplit(endpoint)
    if parsed_endpoint.scheme != "wss" or not parsed_endpoint.netloc:
        raise ConfigError("qwen.endpoint 必须是完整的 WSS URL")

    return QwenConfig(
        api_key=api_key,
        model=model,
        endpoint=endpoint,
        voiceprint_audio_urls=tuple(urls),
    )


def _string_field(section: dict[str, object], name: str, default: str) -> str:
    value = section.get(name, default)
    if not isinstance(value, str):
        raise ConfigError(f"qwen.{name} 必须是字符串")
    return value.strip()
