# Qwen-Audio-Realtime 声纹过滤初测（2026-09-21）

## 测试条件

- 模型：`qwen-audio-3.1-realtime-plus`，WebSocket `smart_turn` 模式。
- 数据：REAL-T 中文 AliMeeting DEV 集，3 段真实会议混合录音，各配一个目标说话人声纹 WAV。
- 输入：16 kHz、16-bit、单声道 PCM；按 100 ms 分片实时发送，末尾补 2 秒静音。
- 声纹 URL：数据集现有的 `hf-mirror.com` HTTPS 镜像；每次有声纹测试都收到 `voiceprint_audio_list.completed`。
- 完整机器可读结果保存在项目本地 `reports/`，其中含转写正文，Git 忽略该目录。

## 关键发现

1. 部分千问平台页面写 `semantic_vad`，但当前服务端对本模型直接返回 `Unsupported turn_detection.type: 'semantic_vad'`，支持列表包含 `smart_turn`。阿里云百炼的 Qwen-Audio 官方说明也用 `smart_turn + voiceprint_audio_urls`。探针已改用 `smart_turn`。
2. 本机可下载的 Hugging Face 原站声纹 URL，从千问服务器下载时超时。使用数据集现有的 `hf-mirror.com` 镜像 URL 后，声纹注册成功；没有把样本上传到陌生文件托管服务。
3. 千问通用临时文件存储返回私有 `oss://` URL；Realtime 声纹字段明确拒绝这种格式，要求 HTTP(S)。曾对第一段公开声纹样本做一次临时上传兼容性尝试，该私有副本按平台说明 48 小时后自动清理。探针中的该无效上传路径已移除。

| 场景 | 有声纹结果 | 无声纹基线 | 观察 |
| --- | --- | --- | --- |
| 85% 重叠，目标 N_SPK8031 | 声纹注册成功；无有效转写，3 段 ambient | 1 段有效转写、2 段 ambient | 有声纹时目标文本未保留；基线有效转写也并非标注的目标内容 |
| 79% 重叠，目标 N_SPK8072 | 声纹注册成功；无有效转写，1 段 ambient 混合目标与旁人内容 | 未跑 | 目标文本没有进入可展示的有效通道 |
| 75% 重叠，目标 N_SPK8011 | 声纹注册成功；3 段有效转写，包含大部分目标内容，但疑似有旁人词句 | 1 段有效转写，目标与旁人内容混合 | 有一定聚焦效果，但未达到“只显示目标人”的可靠程度 |
| 目标单独说话，使用 85% 案例的声纹录音本身作输入 | 声纹注册成功；有完整转写，同时出现 `turn_invalid` | 未跑 | 能识别目标语音，但有效轮次状态存在歧义，不能据此算成功率 |

## 结论与下一步

这些只是一组极小样本的功能性试验，不是严谨 benchmark。可以确认：API Key、音频流、`smart_turn` 和声纹注册链路工作；不能确认：该云端说话人增强已能稳定满足“嘈杂/重叠环境只输出指定人的文字”。

针对当前最重要的目标说话人过滤需求，暂不把 Qwen 说话人增强作为生产方案。下一轮应并行评测真正的目标说话人提取（TSE）模型，再把提取后的音频送入普通中文 ASR；同时用本人实际录制的目标人单说、旁人单说、交替及重叠发言补充评测。

参考：[REAL-T 数据集](https://huggingface.co/datasets/REAL-TSE/REAL-T)、[Qwen-Audio 官方说明](https://help.aliyun.com/zh/model-studio/qwen-audio-realtime-user-guides)、[千问临时文件说明](https://platform.qianwenai.com/docs/api-reference/more/upload-file-get-temporary-url)。
