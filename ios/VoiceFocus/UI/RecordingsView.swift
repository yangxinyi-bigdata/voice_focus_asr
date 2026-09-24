import SwiftUI

struct RecordingsView: View {
    @Bindable var model: MonitorViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if model.recordings.isEmpty {
                    ContentUnavailableView("还没有录音", systemImage: "waveform", description: Text("监听时点“开始录音”即可保存。"))
                } else {
                    List {
                        ForEach(model.recordings, id: \.self) { url in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(url.deletingPathExtension().lastPathComponent)
                                    Text(fileSize(url))
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                ShareLink(item: url) {
                                    Image(systemName: "square.and.arrow.up")
                                }
                                .buttonStyle(.borderless)
                            }
                        }
                        .onDelete(perform: model.deleteRecordings)
                    }
                }
            }
            .navigationTitle("录音文件")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }

    private func fileSize(_ url: URL) -> String {
        let bytes = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }
}
