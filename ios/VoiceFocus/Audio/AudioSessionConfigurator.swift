import AVFoundation

/// 当前录音输入的来源和格式，用来确认 DJI 接收器是否以双声道接入。
struct InputRouteInfo: Equatable {
    var portName: String
    var isUSB: Bool
    var channels: Int
    var sampleRate: Double

    var isStereo: Bool { channels >= 2 }
}

enum AudioSetupError: LocalizedError {
    case permissionDenied

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "没有麦克风权限。请到“设置 → 隐私与安全性 → 麦克风”中允许本 App。"
        }
    }
}

/// 配置系统音频会话：关闭系统的语音处理，优先选 USB 接收器，并请求双声道。
enum AudioSessionConfigurator {
    static func requestPermission() async -> Bool {
        await AVAudioApplication.requestRecordPermission()
    }

    static func configure() throws -> InputRouteInfo {
        let session = AVAudioSession.sharedInstance()
        // measurement 模式尽量关闭系统自带的降噪、自动增益等处理，保证两路音量差不被改动。
        try session.setCategory(.record, mode: .measurement, options: [])
        try session.setPreferredSampleRate(48_000)
        try session.setActive(true)
        if let usb = session.availableInputs?.first(where: { $0.portType == .usbAudio }) {
            try session.setPreferredInput(usb)
        }
        if session.maximumInputNumberOfChannels >= 2 {
            try session.setPreferredInputNumberOfChannels(2)
        }
        return currentRoute()
    }

    static func currentRoute() -> InputRouteInfo {
        let session = AVAudioSession.sharedInstance()
        let input = session.currentRoute.inputs.first
        return InputRouteInfo(
            portName: input?.portName ?? "无输入",
            isUSB: input?.portType == .usbAudio,
            channels: session.inputNumberOfChannels,
            sampleRate: session.sampleRate
        )
    }

    static func deactivate() {
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
