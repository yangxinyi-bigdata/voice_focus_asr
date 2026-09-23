# 双领夹麦录音规程（第一轮）

术语见 [CONTEXT.md](../../CONTEXT.md)。本规程服务于主场景：目标说话人与用户各戴一个 DJI Mic Mini 2 发射器，接收器以立体声模式把两人分到左右声道。

## 设备设置

- 目标说话人和用户各戴一个发射器，夹在领口偏上、离嘴约 15–20 cm 处；两人面对面，间距约 0.8–1 m，模拟餐桌。
- 接收器切到**立体声**模式，每个发射器对应一个固定声道。第一次录音开头让两人分别说“我是左声道 / 我是右声道”，并把对应关系记进清单。
- 发射器降噪设为**关闭**；降噪留到服务器上做有/无对照。增益以大声说话不削波为准。
- 第一轮建议把手机版接收器插在 Mac 上录音，便于直接得到双声道 WAV：

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

```bash
ffmpeg -f avfoundation -i ":<DJI 设备编号>" -ac 2 -ar 48000 -c:a pcm_s24le data/lavalier/round1/target_only_01.wav
```

录完立即检查声道是否真的分离：

```bash
uv run voice-focus-asr inspect-stereo --audio-file data/lavalier/round1/target_only_01.wav --target-channel left
```

`channel_correlation` 接近 1，或出现“两声道几乎相同”警告，说明接收器不在立体声模式，后续录音都无效。iPhone 上能否以双声道提供给第三方 App 需另行验证，不影响第一轮离线数据。

## 声纹样本

目标说话人和用户**各录一段**，用户的是负样本。

- 安静房间，**用同一个发射器、同样的佩戴位置**录制，不要换成手机麦克风，避免声纹样本和测试录音的设备差异。
- 20–30 秒自然说话，无背景音乐、无人插话，内容与测试录音不同。
- 不从混合测试录音中截取。
- 另从中截一段干净的 3–4 秒片段备用：Xiaomi-CocktailASR-1 只使用 1–4 秒参考音频，超出部分会被随机截取，固定片段才能复现结果。

## 第一轮测试录音

安静房间，每类 3 段，共 12 段，每段 10–20 秒。第一轮建议照稿朗读，逐字记录两人各自的文本，便于直接计算 CER 和泄漏率；自由聊天放到后续轮次。稿子见 [第一轮录音稿](./lavalier_round1_scripts.md)。

**每段都由两人同时佩戴发射器、立体声录制**，单说场景也一样：不说话一方的声道记录了串音，是计算能量比和泄漏的依据。

| 类型 | 录制内容 | 验证目标 |
| --- | --- | --- |
| 目标单说 | 只有目标说话人说话 | 完整保留，作为正向基线 |
| 用户单说 | 只有用户说话，目标说话人完全不出声 | 不应显示任何文字；这是最关键的负例 |
| 交替说话 | 两人轮流说，句间可以紧接 | 只保留目标说话人的句子 |
| 同时说话 | 两人同时读不同内容 | 恢复目标说话人的内容；核心难题 |

## 后续轮次

完整的多场景录制计划见 [双领夹麦完整录音计划](./lavalier_full_recording_plan.md)，包括播放噪声、真实餐馆、户外等场景，以及几何与佩戴变量、边界用例和额外录音设备。

## 文件组织

录音放在 `data/lavalier/<轮次>/`（Git 忽略），同目录维护 `manifest.tsv`：

```text
file	case	target_channel	noise	target_text	user_text
target_only_01.wav	target_only	left	quiet	……	
user_only_01.wav	user_only	left	quiet		……
```

`case` 取值：`target_only`、`user_only`、`alternating`、`overlap`。声纹样本单独放在 `data/lavalier/enrollment/`。录音涉及他人声音，须事先取得对方同意，不上传到公开位置。
