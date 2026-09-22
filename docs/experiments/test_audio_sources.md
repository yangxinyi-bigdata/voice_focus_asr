# 可用的目标说话人测试音频

## 首选：REAL-T 的中文 DEV 样本

[REAL-T 官方数据集](https://huggingface.co/datasets/REAL-TSE/REAL-T)直接提供成对的：

- `mixtures/*.wav`：真实多人对话混合音频，含自然重叠、混响和背景声。
- `enrolment_speakers/*.wav`：目标说话人在不重叠时的独立语音，可作为声纹样本。
- `DEV/*_meta.csv`：每组 mix–enroll 配对、语言、目标说话人、目标文本及重叠比例等标注。

官方说明：DEV 有 721 个中文配对；混合录音平均约 17 秒、声纹样本平均约 10 秒、平均重叠比例约 49%。所有音频均为 16 kHz、单声道、16-bit PCM WAV，可直接作为本项目探针的本地 `--audio-file` 输入。REAL-T 不提供真实干净的目标说话人音轨，因此适合评估目标文本保留与旁人文本泄漏，不适合用波形误差评价分离质量。

建议只取少量中文 DEV 样本，不要一开始下载整个语料库：

1. 在数据集文件页取得 `REAL-T-dev/DEV/AliMeeting_meta.csv` 或 `AISHELL-4_meta.csv`。
2. 从 CSV 中选 `language=zh`、`mixture_ratio` 较高的几行，记录 `mixture_utterance` 和 `enrolment_speakers_utterance`。
3. 在同一数据集的 `REAL-T-dev/mixtures/` 与 `REAL-T-dev/enrolment_speakers/` 中下载同名 `.wav`，放入项目的 `data/real-t/`；这个目录不会被 Git 提交。
4. 将声纹 WAV 放在服务端可访问的公开 HTTPS 地址，并把 URL 填入 `config.local.toml` 的 `voiceprint_audio_urls`；本地 `mixture` WAV 作为 `probe-qwen --audio-file` 输入。
5. 用 `ground_truth_transcript` 核对目标文本是否保留，再人工检查有没有旁人的文字漏进有效转写。一定要与不带声纹的基线比较。

下载单个文件可使用 Hugging Face 的 `hf download`，例如先取元数据：

```bash
hf download REAL-TSE/REAL-T REAL-T-dev/DEV/AliMeeting_meta.csv \
  --repo-type dataset --local-dir data/real-t
```

音频文件名确定后，对相应 `.wav` 重复该命令。2026-09-21 开启代理后，本项目已成功下载 3 组中文 DEV 配对，文件位于 `data/real-t/REAL-T-dev/`（Git 忽略）。

| 场景 | 混合录音（`mixtures/`） | 目标声纹（`enrolment_speakers/`） | 重叠比例 |
| --- | --- | --- | --- |
| `alimeeting_overlap_85` | `R8004_M8006_MS805_mixture_1713.06_1726.48.wav` | `R8004_M8006_MS805_N_SPK8031_3.46_11.35.wav` | 85% |
| `alimeeting_overlap_79` | `R8006_M8012_MS803_mixture_177.83_186.62.wav` | `R8006_M8012_MS803_N_SPK8072_2.96_11.62.wav` | 79% |
| `alimeeting_overlap_75` | `R8002_M8003_MS803_mixture_227.50_236.88.wav` | `R8002_M8003_MS803_N_SPK8011_72.22_86.04.wav` | 75% |

六个 WAV 已通过项目探针的 16 kHz、16-bit、单声道校验。第一个声纹文件的 Hugging Face `resolve/main/...wav` 公开 URL 虽然能从本机 GET，但千问服务端下载超时。把域名改为现有公开镜像 `hf-mirror.com` 后，千问声纹注册返回 `voiceprint_audio_list.completed`；这是对该样本的实测，不保证镜像长期可用。

例如第一组声纹 URL 是：

```text
https://hf-mirror.com/datasets/REAL-TSE/REAL-T/resolve/main/REAL-T-dev/enrolment_speakers/R8004_M8006_MS805_N_SPK8031_3.46_11.35.wav
```

REAL-T 为 CC BY-SA 4.0，DEV 可用于模型比较和验证，不能用于训练/微调。原作者也明确提示：版权许可不自动豁免说话人隐私或人格权。向第三方云 API 传输音频前，请自行核对数据集与服务条款。资料：[REAL-T 数据集卡](https://huggingface.co/datasets/REAL-TSE/REAL-T)、[REAL-TSE Challenge](https://real-tse.github.io/challenge/)。

## 备选：原始中文会议语料

- [AliMeeting / OpenSLR 119](https://www.openslr.org/119/)：真实中文会议，2–4 人，包含远场阵列与各人的头戴麦克风录音，标注与重叠场景丰富，许可为 CC BY-SA 4.0；但官方压缩包至少数 GB，不适合最初的轻量试验。
- [AISHELL-4 / OpenSLR 111](https://www.openslr.org/111/)：中文会议，4–8 人、阵列录音与说话人标注，许可为 CC BY-SA 4.0；同样体积较大，也需要自己裁切和匹配声纹片段。

REAL-T 已预先做好“混合音频＋目标声纹”的配对，因此应先用 REAL-T，避免一上来整理整套会议语料。

## 仍建议补录真实使用场景

公开数据集不能代表你的 iPhone 麦克风、人与手机距离、咖啡馆/街道噪声或特定用户声音。最终至少补录：目标人单说、旁人单说、交替发言、同时发言、旁人更响的同时发言。声纹样本尽量在安静环境中录制，并取得被录音人的同意。
