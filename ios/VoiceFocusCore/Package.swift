// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VoiceFocusCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "VoiceFocusCore", targets: ["VoiceFocusCore"]),
    ],
    targets: [
        .target(name: "VoiceFocusCore"),
        .testTarget(name: "VoiceFocusCoreTests", dependencies: ["VoiceFocusCore"]),
    ]
)
