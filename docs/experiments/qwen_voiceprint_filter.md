# Qwen-Audio-Realtime 声纹过滤实验

## 实验目的

本实验只回答一个问题：注册目标说话人的声纹后，Qwen-Audio-Realtime 能否在嘈杂、多人和重叠发言条件下做到“目标人正常出字、旁人不出字”。

它不是语音识别模型横评，也不把一般中文 ASR 准确率作为当前验收重点。

## 能力边界

`smart_turn` 根据声学和语义信息判断一轮有效发言何时开始、结束，以及声音是否足以形成有效轮次。`voiceprint_audio_urls` 在首次 `session.update` 中注册目标说话人的声纹，供服务端进行说话人增强。

服务端可能把输入归为：

- `accepted`：产生 `conversation.item.input_audio_transcription.completed`，表示输入被当作有效发言并转写。
- `rejected_or_ambient`：产生 ambient transcription，或以 `turn_invalid` 停止，表示输入没有进入有效轮次。
- `mixed`：同一测试文件中既有接受结果又有拒绝/环境声结果。
- `ambiguous_accepted_with_invalid_turn`：同时出现 completed 转写与 `turn_invalid`，需要按事件顺序人工核对，不能直接算作有效识别。
- `no_decision`：超时前没有得到可判定事件，需要检查录音、端点检测或协议兼容性。

这项 API 不返回分离后的目标说话人波形，不能当成真正的 Speech Separation 或 Target Speaker Extraction。若它无法满足拒识指标，下一阶段再评测 WeSep/ClearerVoice 一类目标说话人提取模型。

注意：`rejected_or_ambient` 只是一次会话的事件分类，不单独证明“因声纹不匹配而拒绝”。必须对同一录音比较有声纹和无声纹结果，并核对目标文本与旁人文本。

协议勘误：千问平台部分文档写 `semantic_vad`，但 2026-09-21 对 `qwen-audio-3.1-realtime-plus` 的实际调用返回 `Unsupported turn_detection.type: 'semantic_vad'`，列出 `server_vad`、`smart_turn`、`smart_turn_v2`。阿里云百炼的 Qwen-Audio 官方指南在说话人增强示例中使用 `smart_turn + voiceprint_audio_urls`，因此探针改用 `smart_turn`。这只验证了参数兼容性，不代表声纹过滤效果已经通过测试。

## 输入要求

- 测试音频：16 kHz、16-bit、单声道、未压缩 WAV。
- 声纹样本：干净的目标说话人录音，转换为 16 kHz PCM/WAV，并放到无需鉴权、服务端可以访问的 HTTPS URL。
- 千问通用临时上传返回的 `oss://` URL **不能**用于这里：2026-09-21 Realtime 服务端实测返回 `voiceprint_audio_urls must contain valid http(s) URL strings`。因此声纹必须托管到千问服务端能下载的公网 HTTP(S) 地址。
- 声纹 URL 最多 5 个，只能在第一次 `session.update` 中提交。
- API Key 填写在项目根目录的 `config.local.toml`（已被 Git 忽略）。`DASHSCOPE_API_KEY` 环境变量可临时覆盖，禁止写入仓库。

可用语料与许可见 [测试音频来源](./test_audio_sources.md)。

## 最小测试矩阵

每个场景先跑一次无声纹基线，再跑一次同音频有声纹实验：

| 场景 | 期望结果 | 核心指标 |
| --- | --- | --- |
| 目标人单独说话 | accepted | 目标接受率、文本完整度 |
| 旁人单独说话 | rejected_or_ambient | 旁人拒绝率 |
| 目标人 + 稳态噪声 | accepted | 不同 SNR 下目标接受率 |
| 目标人、旁人交替 | 只接受目标人片段 | 旁人文本泄漏率 |
| 目标人、旁人同时说话 | 尽量只保留目标人 | 重叠语音目标保留率、旁人泄漏率 |
| 旁人更响的重叠语音 | 尽量只保留目标人 | 声强劣势下的鲁棒性 |

建议至少测试 3 名旁人，噪声场景覆盖安静、咖啡馆和道路声；混音 SNR 可从 `+10 / +5 / 0 / -5 dB` 开始。

## 运行命令

安装完整依赖，在 `config.local.toml` 的 `[qwen] api_key` 中填写密钥：

```bash
uv sync --all-extras
```

有声纹实验：

```bash
uv run voice-focus-asr probe-qwen \
  --label target_clean \
  --audio-file ./data/cases/target_clean.wav \
  --output ./reports/target_clean.with_voiceprint.json
```

无声纹基线：

```bash
uv run voice-focus-asr probe-qwen \
  --label target_clean_baseline \
  --without-voiceprint \
  --audio-file ./data/cases/target_clean.wav \
  --output ./reports/target_clean.baseline.json
```

上面的 `--without-voiceprint` 会忽略配置文件中的声纹列表。若配置文件的 `voiceprint_audio_urls=[]`，直接省略该参数即可。运行前应把 `target_clean.wav` 换成实际下载或录制的测试文件。

探针默认按真实时间发送 100 ms PCM 分片，并在末尾发送 2 秒静音以触发端点判断。输出包含转写正文，报告文件不要提交或公开分享。

## 第一阶段 Go / No-Go 建议

在代表性录音上同时满足以下条件才进入产品 Adapter：

- 目标人单说及 `0 dB` 常见噪声下的接受率达到可用水平。
- 旁人单说的文本泄漏率足够低。
- 交替发言中旁人内容不会混入目标文本。
- 重叠发言测试结果至少优于“无声纹基线”；若仍大量泄漏，则直接进入本地目标说话人提取评测。

具体阈值需要用真实使用环境的容错要求确定，不应仅凭单段演示录音下结论。
