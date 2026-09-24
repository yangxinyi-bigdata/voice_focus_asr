import Foundation

/// 管理保存在 App“文稿/Recordings”目录中的录音。该目录在“文件”App 中可见。
enum RecordingStore {
    static var directory: URL {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return documents.appendingPathComponent("Recordings", isDirectory: true)
    }

    /// 根据用户输入的名称生成不重名的 WAV 路径；空名称时使用时间戳。
    static func newFileURL(named rawName: String, now: Date = Date()) throws -> URL {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let base = sanitized(rawName).isEmpty ? defaultName(now: now) : sanitized(rawName)
        var candidate = directory.appendingPathComponent(base).appendingPathExtension("wav")
        var suffix = 2
        while FileManager.default.fileExists(atPath: candidate.path) {
            candidate = directory.appendingPathComponent("\(base)-\(suffix)").appendingPathExtension("wav")
            suffix += 1
        }
        return candidate
    }

    static func list() -> [URL] {
        let keys: [URLResourceKey] = [.creationDateKey]
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: keys
        )) ?? []
        return urls
            .filter { $0.pathExtension.lowercased() == "wav" }
            .sorted { creationDate($0) > creationDate($1) }
    }

    /// 去掉文件名中不允许或易出错的字符，空格替换为下划线。
    static func sanitized(_ name: String) -> String {
        let forbidden = CharacterSet(charactersIn: "/\\:?*\"<>|")
        return name
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .components(separatedBy: forbidden).joined()
            .replacingOccurrences(of: " ", with: "_")
    }

    private static func defaultName(now: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        return "录音_\(formatter.string(from: now))"
    }

    private static func creationDate(_ url: URL) -> Date {
        (try? url.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
    }
}
