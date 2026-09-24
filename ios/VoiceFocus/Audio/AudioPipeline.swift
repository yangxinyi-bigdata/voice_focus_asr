import AVFoundation
import VoiceFocusCore

/// 一帧分析结果，送回主线程刷新界面。
struct FrameReport {
    var levels: ChannelLevels
    var activity: SpeakerActivity
    var userVoiceInTargetMicDB: Double?
    var targetVoiceInUserMicDB: Double?
}

/// 采集双声道音频，逐帧判断谁在说话，并可同时把原始双声道写入文件。
///
/// 音频回调运行在系统音频线程上；与主线程共享的状态都由 `lock` 保护。
final class AudioPipeline: @unchecked Sendable {
    private let lock = NSLock()
    private var engine: AVAudioEngine?
    private var accumulator = FrameLevelAccumulator(sampleRate: 48_000)
    private var classifier = SpeakerActivityClassifier()
    private var smoother = ActivitySmoother()
    private var targetChannelIndex = 0
    private var recordingFile: AVAudioFile?

    /// 每凑满一帧（100 ms）调用一次，在主线程执行。
    var onFrame: (@MainActor (FrameReport) -> Void)?

    private(set) var inputFormat: AVAudioFormat?

    func start(settings: ActivitySettings, targetIsLeft: Bool) throws {
        stop()
        let engine = AVAudioEngine()
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        lock.withLock {
            accumulator = FrameLevelAccumulator(sampleRate: format.sampleRate)
            classifier = SpeakerActivityClassifier(settings: settings)
            smoother = ActivitySmoother()
            targetChannelIndex = targetIsLeft ? 0 : 1
            inputFormat = format
        }
        let bufferSize = AVAudioFrameCount(format.sampleRate / 10)
        input.installTap(onBus: 0, bufferSize: bufferSize, format: format) { [weak self] buffer, _ in
            self?.process(buffer)
        }
        engine.prepare()
        try engine.start()
        self.engine = engine
    }

    func stop() {
        stopRecording()
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        engine = nil
    }

    func update(settings: ActivitySettings, targetIsLeft: Bool) {
        lock.withLock {
            classifier.settings = settings
            let index = targetIsLeft ? 0 : 1
            if index != targetChannelIndex {
                targetChannelIndex = index
                classifier.resetLearning()
            }
        }
    }

    /// 以 24-bit WAV 保存原始双声道（声道顺序与接收器一致，不受“对方在左/右”设置影响）。
    func startRecording(to url: URL) throws {
        guard let format = inputFormat else { return }
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: format.sampleRate,
            AVNumberOfChannelsKey: format.channelCount,
            AVLinearPCMBitDepthKey: 24,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]
        let file = try AVAudioFile(
            forWriting: url,
            settings: settings,
            commonFormat: format.commonFormat,
            interleaved: format.isInterleaved
        )
        lock.withLock { recordingFile = file }
    }

    func stopRecording() {
        // AVAudioFile 在释放时写完文件头。
        lock.withLock { recordingFile = nil }
    }

    private func process(_ buffer: AVAudioPCMBuffer) {
        guard let channels = buffer.floatChannelData else { return }
        let frameCount = Int(buffer.frameLength)
        let channelCount = Int(buffer.format.channelCount)

        let reports: [FrameReport] = lock.withLock {
            try? recordingFile?.write(from: buffer)
            let targetIndex = min(targetChannelIndex, channelCount - 1)
            let userIndex = channelCount >= 2 ? 1 - targetIndex : 0
            let target = Array(UnsafeBufferPointer(start: channels[targetIndex], count: frameCount))
            let user = Array(UnsafeBufferPointer(start: channels[userIndex], count: frameCount))
            return accumulator.append(target: target, user: user).map { levels in
                let activity = smoother.smooth(classifier.classify(levels))
                return FrameReport(
                    levels: levels,
                    activity: activity,
                    userVoiceInTargetMicDB: classifier.userVoiceInTargetMicDB,
                    targetVoiceInUserMicDB: classifier.targetVoiceInUserMicDB
                )
            }
        }
        guard !reports.isEmpty, let onFrame else { return }
        Task { @MainActor in
            for report in reports {
                onFrame(report)
            }
        }
    }
}
