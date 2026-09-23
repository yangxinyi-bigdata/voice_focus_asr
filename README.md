# Voice Focus ASR

面向嘈杂、多人说话环境的目标说话人实时转写项目。

项目将“听谁”和“听懂什么”拆成两个独立能力：

1. 目标说话人处理：利用预注册声纹增强、筛选或提取目标用户语音。
2. 流式语音识别：把处理后的中文语音实时转换成增量文本和最终文本。

## 当前状态与第一优先级

当前第一优先级不是比较通用 ASR，而是验证“目标说话人过滤”是否成立：

- 给定目标用户声纹后，目标用户说话应正常出字。
- 旁人单独说话应被拒绝，不应产生有效转写。
- 噪声、交替发言和重叠发言中，应尽量保留目标用户文字并抑制旁人文字。

仓库已经提供：

- 明确 diarization、语音分离和目标说话人提取的领域边界。
- 定义音频、目标声纹、转写事件等稳定数据契约。
- 定义目标说话人处理器和流式识别器的可替换端口。
- 提供会话状态机、顺序校验、完成与中止语义。
- 提供透传处理器用于打通链路和建立无过滤基线。
- 提供 Qwen-Audio-Realtime `smart_turn + voiceprint_audio_urls` 能力探针。
- 提供诊断 CLI、单元测试和持续集成配置。

探针会连接真实千问 API，但它仍是实验工具，不代表这项能力已通过生产验收。

## Qwen 声纹过滤探针

千问方案把两项能力组合在同一实时会话中：

- `smart_turn`：结合声学和语义信息判断有效发言轮次。
- `voiceprint_audio_urls`：首次建立会话时注册目标用户声纹，尝试抑制旁人和背景声。
- 流式发送 16 kHz、16-bit、单声道 PCM。
- 观察有效转写、ambient transcription 和 `turn_invalid` 事件。

它不输出分离后的目标音轨。因此本阶段先验证“只输出目标人的文字”是否可靠；若重叠发言仍有明显旁人泄漏，再评测 WeSep、ClearerVoice 等真正的目标说话人提取模型。

完整实验矩阵和命令见 [Qwen 声纹过滤实验](./docs/experiments/qwen_voiceprint_filter.md)。
现成中文多人语料见 [测试音频来源](./docs/experiments/test_audio_sources.md)。
第一轮真实调用与局限见 [声纹过滤初测](./docs/experiments/qwen_voiceprint_initial_results_2026-09-21.md)。

## 环境

要求 Python 3.12。推荐使用 `uv`：

```bash
uv sync --all-extras
uv run voice-focus-asr doctor
uv run pytest
```

在项目根目录的 `config.local.toml` 中填写 `[qwen] api_key`。该本地文件已被 Git 忽略，仓库只提交 [config.example.toml](./config.example.toml) 模板。运行 `probe-qwen` 时会自动读取配置；`--config` 可指定其他路径，`DASHSCOPE_API_KEY` 环境变量可临时覆盖文件中的密钥。

也可以使用普通虚拟环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,qwen]'
voice-focus-asr doctor
pytest
```

## 目录结构

```text
src/voice_focus_asr/
├── adapters/       # 云端和本地模型 Adapter
├── contracts.py    # 稳定领域契约
├── ports.py        # 目标说话人处理与 ASR 端口
├── session.py      # 会话状态机和编排
└── cli.py          # 本地诊断入口
tests/              # 单元测试
docs/adr/           # 架构决策
```

如果刚接触语音技术，先读 [CONTEXT.md](./CONTEXT.md) 中的术语解释，再看[餐馆与多人环境方案分析](./docs/experiments/target_speaker_options_2026-09-22.md)。架构决策见 [docs/adr/0001-separate-speaker-focus-from-asr.md](./docs/adr/0001-separate-speaker-focus-from-asr.md)。

## 音频契约

基础链路固定接收：

- PCM signed 16-bit little-endian
- 16,000 Hz
- 单声道
- 严格递增的音频分片序号

平台采集层负责把麦克风输入转换到该格式。API Key、声纹录音和原始音频不得写入日志或提交到仓库。
