import Foundation

/// 一帧内目标麦克风与参考麦克风的音量，单位 dBFS。
public struct ChannelLevels: Equatable, Sendable {
    public let targetDB: Double
    public let userDB: Double

    public init(targetDB: Double, userDB: Double) {
        self.targetDB = targetDB
        self.userDB = userDB
    }

    /// 目标声道比参考声道响多少 dB；正值表示对方的麦更响。
    public var differenceDB: Double { targetDB - userDB }
}

/// 把连续到达的双声道样本切成固定时长的帧，逐帧输出两个声道的 RMS 音量。
///
/// 与 Python 端 `inspect-stereo` 使用相同的 100 ms 帧长和 -120 dBFS 下限，
/// 保证手机上的实时判断与离线分析可以直接对照。
public struct FrameLevelAccumulator: Sendable {
    public static let floorDB = -120.0

    public let frameSize: Int
    private var targetSumSquares = 0.0
    private var userSumSquares = 0.0
    private var count = 0

    public init(sampleRate: Double, frameDuration: Double = 0.1) {
        precondition(sampleRate > 0 && frameDuration > 0)
        frameSize = max(1, Int((sampleRate * frameDuration).rounded()))
    }

    /// 追加一段样本（两个声道长度必须相同），返回这段样本凑满的所有帧。
    public mutating func append(target: [Float], user: [Float]) -> [ChannelLevels] {
        precondition(target.count == user.count, "两个声道的样本数必须相同")
        var frames: [ChannelLevels] = []
        for index in target.indices {
            let t = Double(target[index])
            let u = Double(user[index])
            targetSumSquares += t * t
            userSumSquares += u * u
            count += 1
            if count == frameSize {
                frames.append(ChannelLevels(
                    targetDB: Self.decibels(meanSquare: targetSumSquares / Double(frameSize)),
                    userDB: Self.decibels(meanSquare: userSumSquares / Double(frameSize))
                ))
                targetSumSquares = 0
                userSumSquares = 0
                count = 0
            }
        }
        return frames
    }

    public static func decibels(meanSquare: Double) -> Double {
        meanSquare > 0 ? max(floorDB, 10 * log10(meanSquare)) : floorDB
    }
}
