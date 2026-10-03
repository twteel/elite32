import SwiftUI

struct GameDetailView: View {
    @Environment(ScoreStore.self) private var store
    let gameID: Int

    var body: some View {
        if let game = store.game(id: gameID) {
            ScrollView {
                VStack(spacing: 24) {
                    StatusPill(game: game)

                    HStack(alignment: .top) {
                        BigTeam(name: game.awayTeam, label: "AWAY", score: game.awayScore, showScore: game.hasScore, dimmed: game.winner == .home)
                        Text("–").font(.largeTitle).foregroundStyle(.secondary).padding(.top, 36)
                        BigTeam(name: game.homeTeam, label: "HOME", score: game.homeScore, showScore: game.hasScore, dimmed: game.winner == .away)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        if !game.eventName.isEmpty { InfoRow(icon: "trophy", text: game.eventName) }
                        if !game.division.isEmpty { InfoRow(icon: "person.3", text: game.division) }
                        if !game.venue.isEmpty { InfoRow(icon: "mappin.and.ellipse", text: game.venue) }
                        if let start = game.startsAt {
                            InfoRow(icon: "calendar", text: start.formatted(date: .complete, time: .shortened))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.e32Card, in: RoundedRectangle(cornerRadius: 16))
                }
                .padding()
            }
            .navigationTitle(game.division.isEmpty ? "Game" : game.division)
            .navigationBarTitleDisplayMode(.inline)
            .refreshable { await store.refresh() }
        } else {
            ContentUnavailableView("Game removed", systemImage: "xmark.circle")
        }
    }
}

private struct BigTeam: View {
    let name: String
    let label: String
    let score: Int
    let showScore: Bool
    let dimmed: Bool

    var body: some View {
        VStack(spacing: 6) {
            Text(label).font(.caption2.weight(.bold)).tracking(2).foregroundStyle(.secondary)
            Text(showScore ? "\(score)" : "–")
                .font(.system(size: 64, weight: .heavy))
                .monospacedDigit()
                .contentTransition(.numericText(value: Double(score)))
                .animation(.snappy, value: score)
            Text(name)
                .font(.headline)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .opacity(dimmed ? 0.55 : 1)
    }
}

private struct InfoRow: View {
    let icon: String
    let text: String

    var body: some View {
        Label(text, systemImage: icon).font(.subheadline)
    }
}
