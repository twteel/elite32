import SwiftUI

@main
struct Elite32ScoresApp: App {
    @State private var store = ScoreStore()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
                .preferredColorScheme(.dark)
                .tint(.e32Pink)
        }
        .onChange(of: scenePhase, initial: true) { _, phase in
            // Only poll while the app is on screen; refresh right away when it comes back.
            if phase == .active {
                store.startPolling()
            } else {
                store.stopPolling()
            }
        }
    }
}

struct RootView: View {
    var body: some View {
        TabView {
            ScoresView()
                .tabItem { Label("Scores", systemImage: "sportscourt") }
            ScorekeeperView()
                .tabItem { Label("Scorekeeper", systemImage: "square.and.pencil") }
        }
    }
}

extension Color {
    /// Elite 32 brand pink (matches the website).
    static let e32Pink = Color(red: 0xEE / 255, green: 0x3A / 255, blue: 0x68 / 255)
    static let e32Card = Color(white: 0.07)
}
