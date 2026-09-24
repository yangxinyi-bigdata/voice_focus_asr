import SwiftUI

struct SettingsView: View {
    @Bindable var model: MonitorViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("对方的麦克风", selection: $model.targetIsLeft) {
                        Text("左声道").tag(true)
                        Text("右声道").tag(false)
                    }
                } footer: {
                    Text("与发射器标签一致：默认左声道 = 对方，右声道 = 我。切换后会重新学习串音强度。")
                }

                Section {
                    Stepper(value: $model.silenceDBFS, in: -70 ... -30, step: 1) {
                        LabeledContent("安静阈值", value: "\(Int(model.silenceDBFS)) dBFS")
                    }
                    Stepper(value: $model.dominanceDB, in: 3 ... 15, step: 1) {
                        LabeledContent("单人判定音量差", value: "\(Int(model.dominanceDB)) dB")
                    }
                } header: {
                    Text("判定参数")
                } footer: {
                    Text("两路都低于安静阈值时算“安静”；一路比另一路响出“单人判定音量差”以上，才算只有这一方在说。")
                }
            }
            .navigationTitle("设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}
