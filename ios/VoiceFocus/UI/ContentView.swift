import SwiftUI
import VoiceFocusCore

struct ContentView: View {
    @State private var model = MonitorViewModel()
    @State private var showingSettings = false
    @State private var showingRecordings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    RouteCard(route: model.route, isMonitoring: model.isMonitoring)
                    ActivityBanner(activity: model.activity, isMonitoring: model.isMonitoring)
                    LevelsCard(
                        levels: model.levels,
                        targetIsLeft: model.targetIsLeft,
                        userVoiceInTargetMicDB: model.userVoiceInTargetMicDB,
                        targetVoiceInUserMicDB: model.targetVoiceInUserMicDB
                    )
                    ActivityStatsCard(counts: model.activityCounts)
                    RecordingCard(model: model)
                    if let message = model.errorMessage {
                        Text(message)
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding()
            }
            .safeAreaInset(edge: .bottom) {
                Button {
                    Task { await model.toggleMonitoring() }
                } label: {
                    Text(model.isMonitoring ? "停止监听" : "开始监听")
                        .font(.title2.bold())
                        .frame(maxWidth: .infinity, minHeight: 56)
                }
                .buttonStyle(.borderedProminent)
                .tint(model.isMonitoring ? .red : .accentColor)
                .padding()
                .background(.bar)
            }
            .navigationTitle("Voice Focus")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("录音文件") { showingRecordings = true }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("设置") { showingSettings = true }
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView(model: model)
            }
            .sheet(isPresented: $showingRecordings) {
                RecordingsView(model: model)
            }
        }
    }
}

private struct RouteCard: View {
    let route: InputRouteInfo?
    let isMonitoring: Bool

    var body: some View {
        Card {
            if let route, isMonitoring {
                VStack(alignment: .leading, spacing: 6) {
                    Label(route.portName, systemImage: route.isUSB ? "cable.connector" : "mic")
                        .font(.headline)
                    Text("\(route.channels) 声道 · \(Int(route.sampleRate)) Hz · \(route.isUSB ? "USB" : "非 USB 输入")")
                        .foregroundStyle(.secondary)
                    if !route.isStereo {
                        Text("没有拿到双声道：请确认接收器已插好并处于立体声模式。")
                            .foregroundStyle(.orange)
                    }
                }
            } else {
                Text("插好 DJI 接收器后点“开始监听”。")
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct ActivityBanner: View {
    let activity: SpeakerActivity
    let isMonitoring: Bool

    var body: some View {
        Text(isMonitoring ? activity.title : "未监听")
            .font(.system(size: 44, weight: .bold))
            .frame(maxWidth: .infinity, minHeight: 110)
            .foregroundStyle(.white)
            .background(isMonitoring ? activity.color : .gray, in: RoundedRectangle(cornerRadius: 16))
            .animation(.easeOut(duration: 0.15), value: activity)
            .accessibilityLabel("当前状态：\(isMonitoring ? activity.title : "未监听")")
    }
}

private struct LevelsCard: View {
    let levels: ChannelLevels
    let targetIsLeft: Bool
    let userVoiceInTargetMicDB: Double?
    let targetVoiceInUserMicDB: Double?

    var body: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                LevelBar(title: "对方（\(targetIsLeft ? "左" : "右")声道）", db: levels.targetDB, color: .green)
                LevelBar(title: "我（\(targetIsLeft ? "右" : "左")声道）", db: levels.userDB, color: .blue)
                Text("音量差：\(formatted(hasSignal ? levels.differenceDB : nil)) dB（正数表示对方的麦更响）")
                    .font(.subheadline)
                Divider()
                Text("我的声音进入对方麦：\(formatted(userVoiceInTargetMicDB)) dB")
                Text("对方的声音进入我的麦：\(formatted(targetVoiceInUserMicDB)) dB")
                Text("数值越负越好；约 −10 dB 以下即可可靠区分两人。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var hasSignal: Bool {
        max(levels.targetDB, levels.userDB) > FrameLevelAccumulator.floorDB
    }

    private func formatted(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%.1f", value)
    }
}

private struct LevelBar: View {
    let title: String
    let db: Double
    let color: Color

    /// 把 -60…0 dBFS 映射到 0…1。
    private var fraction: Double { min(1, max(0, (db + 60) / 60)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                Spacer()
                Text(db <= FrameLevelAccumulator.floorDB ? "—" : String(format: "%.1f dBFS", db))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(.systemGray5))
                    Capsule().fill(color).frame(width: proxy.size.width * fraction)
                }
            }
            .frame(height: 14)
        }
    }
}

private struct ActivityStatsCard: View {
    let counts: [SpeakerActivity: Int]

    var body: some View {
        let total = max(1, counts.values.reduce(0, +))
        Card {
            VStack(alignment: .leading, spacing: 6) {
                Text("本次监听统计").font(.headline)
                ForEach(SpeakerActivity.displayOrder, id: \.self) { activity in
                    HStack {
                        Circle().fill(activity.color).frame(width: 10, height: 10)
                        Text(activity.title)
                        Spacer()
                        Text("\(Int(Double(counts[activity, default: 0]) / Double(total) * 100))%")
                            .monospacedDigit()
                    }
                }
            }
        }
    }
}

private struct RecordingCard: View {
    @Bindable var model: MonitorViewModel

    var body: some View {
        Card {
            VStack(alignment: .leading, spacing: 10) {
                Text("录音").font(.headline)
                TextField("文件名，例如 安静包间_对方单说_基准_01_第1遍", text: $model.recordingName)
                    .textFieldStyle(.roundedBorder)
                    .disabled(model.isRecording)
                Button {
                    model.toggleRecording()
                } label: {
                    Label(model.isRecording ? "停止录音" : "开始录音",
                          systemImage: model.isRecording ? "stop.circle.fill" : "record.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(model.isRecording ? .red : .accentColor)
                .disabled(!model.isMonitoring)
                if let url = model.currentRecording {
                    Text("正在录：\(url.lastPathComponent)")
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
                Text("保存为 48 kHz 24-bit 双声道 WAV，可在“文件”App 的“我的 iPhone → Voice Focus → Recordings”中找到。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct Card<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

extension SpeakerActivity {
    static let displayOrder: [SpeakerActivity] = [.target, .user, .both, .silent]

    var title: String {
        switch self {
        case .target: return "对方在说"
        case .user: return "我在说"
        case .both: return "同时在说"
        case .silent: return "安静"
        }
    }

    var color: Color {
        switch self {
        case .target: return .green
        case .user: return .blue
        case .both: return .orange
        case .silent: return .gray
        }
    }
}
