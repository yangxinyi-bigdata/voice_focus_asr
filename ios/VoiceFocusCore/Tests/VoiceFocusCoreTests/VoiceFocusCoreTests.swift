import XCTest
@testable import VoiceFocusCore

final class FrameLevelAccumulatorTests: XCTestCase {
    func testEmitsOneFramePerHundredMilliseconds() {
        var accumulator = FrameLevelAccumulator(sampleRate: 48_000)
        let half = [Float](repeating: 0.5, count: 4_800 + 100)

        let frames = accumulator.append(target: half, user: half.map { $0 * 0.1 })

        XCTAssertEqual(frames.count, 1)
        XCTAssertEqual(frames[0].targetDB, 20 * log10(0.5), accuracy: 0.01)
        XCTAssertEqual(frames[0].differenceDB, 20, accuracy: 0.01)
    }

    func testCarriesPartialFramesAcrossCalls() {
        var accumulator = FrameLevelAccumulator(sampleRate: 16_000)
        let chunk = [Float](repeating: 0.1, count: 1_000)

        XCTAssertTrue(accumulator.append(target: chunk, user: chunk).isEmpty)
        XCTAssertEqual(accumulator.append(target: chunk, user: chunk).count, 1)
    }

    func testSilenceHitsFloor() {
        XCTAssertEqual(FrameLevelAccumulator.decibels(meanSquare: 0), FrameLevelAccumulator.floorDB)
    }
}

final class SpeakerActivityClassifierTests: XCTestCase {
    func testClassifiesSilenceAndSingleTalkers() {
        var classifier = SpeakerActivityClassifier()

        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -70, userDB: -72)), .silent)
        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -20, userDB: -33)), .target)
        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -34, userDB: -20)), .user)
        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -22, userDB: -24)), .both)
    }

    func testLearnsCrosstalkFromSingleTalkerFrames() {
        var classifier = SpeakerActivityClassifier()
        for _ in 0..<20 {
            _ = classifier.classify(ChannelLevels(targetDB: -33.6, userDB: -20))
        }

        XCTAssertEqual(classifier.userVoiceInTargetMicDB ?? 0, -13.6, accuracy: 0.001)
        XCTAssertEqual(classifier.userLeakSampleCount, 20)
        XCTAssertNil(classifier.targetVoiceInUserMicDB)
    }

    func testDetectsOverlapWhenWeakerChannelExceedsExpectedLeak() {
        var classifier = SpeakerActivityClassifier()
        for _ in 0..<20 {
            _ = classifier.classify(ChannelLevels(targetDB: -20, userDB: -33))
        }

        // 只有对方说话时，参考声道约比目标声道低 13 dB；这里只低 7 dB，说明用户也在说。
        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -20, userDB: -27)), .both)
        XCTAssertEqual(classifier.classify(ChannelLevels(targetDB: -20, userDB: -32)), .target)
    }

    func testTranscribeDecision() {
        XCTAssertTrue(SpeakerActivity.target.shouldTranscribe)
        XCTAssertTrue(SpeakerActivity.both.shouldTranscribe)
        XCTAssertFalse(SpeakerActivity.user.shouldTranscribe)
        XCTAssertFalse(SpeakerActivity.silent.shouldTranscribe)
    }
}

final class ActivitySmootherTests: XCTestCase {
    func testSuppressesSingleFrameFlicker() {
        var smoother = ActivitySmoother(window: 3)

        XCTAssertEqual(smoother.smooth(.target), .target)
        XCTAssertEqual(smoother.smooth(.target), .target)
        XCTAssertEqual(smoother.smooth(.user), .target)
        XCTAssertEqual(smoother.smooth(.user), .user)
    }
}
