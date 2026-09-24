import AVFoundation
import Observation
import UIKit
import VoiceFocusCore

@MainActor
@Observable
final class MonitorViewModel {
    private(set) var isMonitoring = false
    private(set) var isRecording = false
    private(set) var route: InputRouteInfo?
    private(set) var levels = ChannelLevels(targetDB: FrameLevelAccumulator.floorDB, userDB: FrameLevelAccumulator.floorDB)
    private(set) var activity: SpeakerActivity = .silent
    private(set) var userVoiceInTargetMicDB: Double?
    private(set) var targetVoiceInUserMicDB: Double?
    private(set) var activityCounts: [SpeakerActivity: Int] = [:]
    private(set) var recordings: [URL] = []
    private(set) var currentRecording: URL?
    var errorMessage: String?

    var recordingName = ""
    var targetIsLeft = true { didSet { pushSettings() } }
    var silenceDBFS = -50.0 { didSet { pushSettings() } }
    var dominanceDB = 6.0 { didSet { pushSettings() } }

    private let pipeline = AudioPipeline()
    private var routeObserver: NSObjectProtocol?

    init() {
        pipeline.onFrame = { [weak self] report in
            self?.apply(report)
        }
        recordings = RecordingStore.list()
    }

    var activitySettings: ActivitySettings {
        ActivitySettings(silenceDBFS: silenceDBFS, dominanceDB: dominanceDB)
    }

    func toggleMonitoring() async {
        if isMonitoring {
            stopMonitoring()
        } else {
            await startMonitoring()
        }
    }

    func startMonitoring() async {
        errorMessage = nil
        guard await AudioSessionConfigurator.requestPermission() else {
            errorMessage = AudioSetupError.permissionDenied.localizedDescription
            return
        }
        do {
            route = try AudioSessionConfigurator.configure()
            try pipeline.start(settings: activitySettings, targetIsLeft: targetIsLeft)
            activityCounts = [:]
            isMonitoring = true
            UIApplication.shared.isIdleTimerDisabled = true
            observeRouteChanges()
        } catch {
            errorMessage = "无法开始监听：\(error.localizedDescription)"
            stopMonitoring()
        }
    }

    func stopMonitoring() {
        if isRecording {
            stopRecording()
        }
        pipeline.stop()
        AudioSessionConfigurator.deactivate()
        if let routeObserver {
            NotificationCenter.default.removeObserver(routeObserver)
        }
        routeObserver = nil
        isMonitoring = false
        activity = .silent
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func toggleRecording() {
        isRecording ? stopRecording() : startRecording()
    }

    func deleteRecordings(at offsets: IndexSet) {
        for index in offsets {
            try? FileManager.default.removeItem(at: recordings[index])
        }
        recordings = RecordingStore.list()
    }

    private func startRecording() {
        guard isMonitoring else { return }
        do {
            let url = try RecordingStore.newFileURL(named: recordingName)
            try pipeline.startRecording(to: url)
            currentRecording = url
            isRecording = true
        } catch {
            errorMessage = "无法开始录音：\(error.localizedDescription)"
        }
    }

    private func stopRecording() {
        pipeline.stopRecording()
        isRecording = false
        currentRecording = nil
        recordings = RecordingStore.list()
    }

    private func apply(_ report: FrameReport) {
        guard isMonitoring else { return }
        levels = report.levels
        activity = report.activity
        userVoiceInTargetMicDB = report.userVoiceInTargetMicDB
        targetVoiceInUserMicDB = report.targetVoiceInUserMicDB
        activityCounts[report.activity, default: 0] += 1
    }

    private func pushSettings() {
        pipeline.update(settings: activitySettings, targetIsLeft: targetIsLeft)
    }

    /// 插拔接收器时重新配置并重启采集，界面上的声道信息随之更新。
    /// 只响应设备插拔：App 自己选择 USB 输入也会触发路由变化，响应它会导致反复重启。
    private func observeRouteChanges() {
        guard routeObserver == nil else { return }
        routeObserver = NotificationCenter.default.addObserver(
            forName: AVAudioSession.routeChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            let rawReason = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt
            let reason = rawReason.flatMap(AVAudioSession.RouteChangeReason.init(rawValue:))
            guard reason == .newDeviceAvailable || reason == .oldDeviceUnavailable else { return }
            Task { @MainActor in
                await self?.restartAfterRouteChange()
            }
        }
    }

    private func restartAfterRouteChange() async {
        guard isMonitoring else { return }
        let wasRecording = isRecording
        stopMonitoring()
        await startMonitoring()
        if wasRecording {
            errorMessage = "输入设备发生变化，录音已停止，请重新开始录音。"
        }
    }
}
