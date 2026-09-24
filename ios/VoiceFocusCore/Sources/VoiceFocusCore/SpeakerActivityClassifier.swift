import Foundation

/// 某一帧里谁在说话。
public enum SpeakerActivity: String, CaseIterable, Sendable {
    case silent
    case target
    case user
    case both

    /// 这一帧的目标声道是否应该送去识别：对方在说或两人同时说时送，只有用户在说或安静时不送。
    public var shouldTranscribe: Bool { self == .target || self == .both }
}

public struct ActivitySettings: Equatable, Sendable {
    /// 两个声道都低于这个音量时视为安静。
    public var silenceDBFS: Double
    /// 一个声道至少比另一个响这么多，才认为只有这一方在说。
    public var dominanceDB: Double
    /// 较弱声道比“纯串音”预期再响这么多，就认为这一方也在说。
    public var overlapMarginDB: Double
    /// 还没学到串音强度时使用的默认值。
    public var defaultCrosstalkDB: Double

    public init(
        silenceDBFS: Double = -50,
        dominanceDB: Double = 6,
        overlapMarginDB: Double = 4,
        defaultCrosstalkDB: Double = -10
    ) {
        self.silenceDBFS = silenceDBFS
        self.dominanceDB = dominanceDB
        self.overlapMarginDB = overlapMarginDB
        self.defaultCrosstalkDB = defaultCrosstalkDB
    }
}

/// 按两个近场麦克风的音量差逐帧判断谁在说话，并在线学习双向串音强度。
///
/// 只有一方在说时，另一方麦克风里的声音就是串音；它比说话人自己的麦克风弱多少 dB
/// 基本稳定。若较弱声道明显高于这个预期，说明另一方也在开口，即两人同时说话。
public struct SpeakerActivityClassifier: Sendable {
    public var settings: ActivitySettings
    private var userLeak = RunningMedian(capacity: 300)
    private var targetLeak = RunningMedian(capacity: 300)

    public init(settings: ActivitySettings = ActivitySettings()) {
        self.settings = settings
    }

    /// 用户的声音进入目标麦克风时，比进入用户自己的麦克风弱多少 dB（负值）。
    public var userVoiceInTargetMicDB: Double? { userLeak.median }
    /// 目标说话人的声音进入用户麦克风时，比进入目标麦克风弱多少 dB（负值）。
    public var targetVoiceInUserMicDB: Double? { targetLeak.median }
    public var userLeakSampleCount: Int { userLeak.count }
    public var targetLeakSampleCount: Int { targetLeak.count }

    public mutating func classify(_ levels: ChannelLevels) -> SpeakerActivity {
        let t = levels.targetDB
        let u = levels.userDB
        if max(t, u) < settings.silenceDBFS {
            return .silent
        }
        let difference = t - u
        if difference >= settings.dominanceDB {
            let expectedLeak = targetLeak.median ?? settings.defaultCrosstalkDB
            if u > t + expectedLeak + settings.overlapMarginDB {
                return .both
            }
            targetLeak.insert(-difference)
            return .target
        }
        if difference <= -settings.dominanceDB {
            let expectedLeak = userLeak.median ?? settings.defaultCrosstalkDB
            if t > u + expectedLeak + settings.overlapMarginDB {
                return .both
            }
            userLeak.insert(difference)
            return .user
        }
        return .both
    }

    public mutating func resetLearning() {
        userLeak = RunningMedian(capacity: userLeak.capacity)
        targetLeak = RunningMedian(capacity: targetLeak.capacity)
    }
}

/// 最近若干帧的多数表决，避免显示在相邻两帧之间来回闪烁。平票时取最新一帧。
public struct ActivitySmoother: Sendable {
    private var history: [SpeakerActivity] = []
    public let window: Int

    public init(window: Int = 3) {
        precondition(window > 0)
        self.window = window
    }

    public mutating func smooth(_ activity: SpeakerActivity) -> SpeakerActivity {
        history.append(activity)
        if history.count > window {
            history.removeFirst(history.count - window)
        }
        var counts: [SpeakerActivity: Int] = [:]
        for item in history {
            counts[item, default: 0] += 1
        }
        let best = counts.values.max() ?? 0
        return counts[activity] == best
            ? activity
            : history.last(where: { counts[$0] == best }) ?? activity
    }
}

/// 固定容量的滑动中位数。
struct RunningMedian: Sendable {
    let capacity: Int
    private var values: [Double] = []
    private var next = 0

    init(capacity: Int) {
        precondition(capacity > 0)
        self.capacity = capacity
    }

    var count: Int { values.count }

    mutating func insert(_ value: Double) {
        if values.count < capacity {
            values.append(value)
        } else {
            values[next] = value
        }
        next = (next + 1) % capacity
    }

    var median: Double? {
        guard !values.isEmpty else { return nil }
        let sorted = values.sorted()
        let middle = sorted.count / 2
        return sorted.count.isMultiple(of: 2)
            ? (sorted[middle - 1] + sorted[middle]) / 2
            : sorted[middle]
    }
}
