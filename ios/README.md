# Voice Focus iOS 原型

第一版只做一件事：在 iPhone 上实时读取 DJI 接收器的双声道，按两路音量差判断“对方在说 / 我在说 / 同时在说 / 安静”，并可把原始双声道保存为 WAV。还没有语音识别。

判断逻辑与 Python 端 `inspect-stereo` 一致（100 ms 帧、-50 dBFS 安静阈值、6 dB 单人判定），放在可以在 Mac 上直接测试的 `VoiceFocusCore` 包里。

## 目录

```text
ios/
├── project.yml            # XcodeGen 工程描述；VoiceFocus.xcodeproj 由它生成，不提交
├── Config/                # 构建设置；Signing.local.xcconfig 保存个人签名团队，不提交
├── VoiceFocus/            # App：音频会话、采集、录音、界面
└── VoiceFocusCore/        # 纯 Swift 逻辑：分帧音量、谁在说话、串音学习
```

## 首次运行

1. 安装 XcodeGen：

   ```bash
   brew install xcodegen
   ```

2. 写入签名团队（团队 ID 可在 Xcode → Settings → Accounts 中查看）：

   ```bash
   echo 'DEVELOPMENT_TEAM = 你的团队ID' > ios/Config/Signing.local.xcconfig
   ```

3. 生成并打开工程：

   ```bash
   cd ios && xcodegen generate && open VoiceFocus.xcodeproj
   ```

4. 用数据线连接 iPhone，在 Xcode 顶部选择这台 iPhone，点运行。首次安装后，需在 iPhone“设置 → 通用 → VPN 与设备管理”中信任开发者。免费 Apple ID 签名的 App 每 7 天需要重新安装一次。

模拟器接不了 USB 麦克风，必须用真机。

## 使用

1. 把 DJI 接收器插到 iPhone，确认接收器为立体声模式，两个发射器降噪关闭、增益相同。
2. 点“开始监听”。顶部卡片应显示接收器名称、`2 声道`、`48000 Hz`、`USB`；如果提示没有拿到双声道，先排查接收器设置。
3. 分别让对方和自己单独说话，确认大色块显示正确；“我的声音进入对方麦”约 -10 dB 以下即可可靠区分两人。
4. 需要保存时，填好文件名再点“开始录音”。录音在“文件”App →“我的 iPhone → Voice Focus → Recordings”中，也可在 App 内的“录音文件”里分享或 AirDrop。

App 监听时屏幕不会自动锁定；锁屏后在后台继续采集和录音。

## 测试

核心逻辑可在 Mac 上直接测试：

```bash
swift test --package-path ios/VoiceFocusCore
```
