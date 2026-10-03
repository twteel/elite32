import SwiftUI

enum ScoreFilter: String, CaseIterable, Identifiable {
    case live = "Live"
    case today = "Today"
    case upcoming = "Upcoming"
    case final = "Final"

    var id: String { rawValue }

    func includes(_ game: Game) -> Bool {
        switch self {
        case .live:
            game.status == .live
        case .today:
            game.startsAt.map(Calendar.current.isDateInToday) ?? false
        case .upcoming:
            game.status == .scheduled || game.status == .postponed
        case .final:
            game.status == .final || game.status == .canceled
        }
    }
}

struct ScoresView: View {
    @Environment(ScoreStore.self) private var store
    @State private var filter: ScoreFilter?

    private var activeFilter: ScoreFilter {
        filter ?? (store.games.contains { $0.status == .live } ? .live : .today)
    }

    private var sections: [(event: String, games: [Game])] {
        let shown = store.games.filter(activeFilter.includes)
        let finalFirst = activeFilter == .final
        var order: [String] = []
        var grouped: [String: [Game]] = [:]
        for game in shown {
            let key = game.eventName.isEmpty ? "Games" : game.eventName
            if grouped[key] == nil { order.append(key) }
            grouped[key, default: []].append(game)
        }
        return order.map { key in
            let games = grouped[key]!
            return (key, finalFirst ? Array(games.reversed()) : games)
        }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Show", selection: Binding(get: { activeFilter }, set: { filter = $0 })) {
                        ForEach(ScoreFilter.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets())
                }

                if let message = store.errorMessage {
                    Section {
                        Label(message, systemImage: "wifi.exclamationmark")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }

                ForEach(sections, id: \.event) { section in
                    Section(section.event) {
                        ForEach(section.games) { game in
                            NavigationLink(value: game.id) {
                                GameRow(game: game)
                            }
                            .listRowBackground(Color.e32Card)
                        }
                    }
                }
            }
            .overlay {
                if sections.isEmpty {
                    if store.lastUpdated == nil && store.isLoading {
                        ProgressView()
                    } else {
                        ContentUnavailableView(
                            "No \(activeFilter.rawValue.lowercased()) games",
                            systemImage: "basketball",
                            description: Text("Scores show up here the moment they're posted.")
                        )
                    }
                }
            }
            .navigationTitle("Elite 32")
            .navigationDestination(for: Int.self) { GameDetailView(gameID: $0) }
            .refreshable { await store.refresh() }
            .safeAreaInset(edge: .bottom) { UpdatedFooter() }
        }
    }
}

struct UpdatedFooter: View {
    @Environment(ScoreStore.self) private var store

    var body: some View {
        if let updated = store.lastUpdated {
            TimelineView(.periodic(from: .now, by: 5)) { _ in
                Text("Updated \(updated, format: .relative(presentation: .named)) · refreshes automatically")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(.bar)
            }
        }
    }
}

struct GameRow: View {
    let game: Game

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                StatusPill(game: game)
                Spacer()
                Text(game.subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            TeamLine(name: game.awayTeam, score: game.awayScore, showScore: game.hasScore, isWinner: game.winner == .away, dimmed: game.winner == .home)
            TeamLine(name: game.homeTeam, score: game.homeScore, showScore: game.hasScore, isWinner: game.winner == .home, dimmed: game.winner == .away)
        }
        .padding(.vertical, 6)
    }
}

struct TeamLine: View {
    let name: String
    let score: Int
    let showScore: Bool
    var isWinner = false
    var dimmed = false

    var body: some View {
        HStack {
            Text(name)
                .font(.body.weight(isWinner ? .bold : .medium))
                .lineLimit(1)
            Spacer()
            if showScore {
                Text("\(score)")
                    .font(.title2.weight(.heavy))
                    .monospacedDigit()
                    .contentTransition(.numericText(value: Double(score)))
            }
        }
        .foregroundStyle(dimmed ? .secondary : .primary)
        .animation(.snappy, value: score)
    }
}

struct StatusPill: View {
    let game: Game

    private var text: String {
        switch game.status {
        case .live:
            game.period.isEmpty ? "LIVE" : "LIVE · \(game.period.uppercased())"
        case .final:
            game.period.uppercased().contains("OT") ? "FINAL/\(game.period.uppercased())" : "FINAL"
        case .scheduled:
            game.startsAt?.formatted(date: .omitted, time: .shortened) ?? "TBA"
        case .postponed, .canceled:
            game.status.label.uppercased()
        }
    }

    var body: some View {
        HStack(spacing: 5) {
            if game.status == .live {
                Circle().fill(.white).frame(width: 6, height: 6)
                    .phaseAnimator([1.0, 0.3]) { dot, opacity in dot.opacity(opacity) }
            }
            Text(text)
        }
        .font(.caption2.weight(.heavy))
        .tracking(1)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(game.status == .live ? Color.e32Pink : Color.white.opacity(0.12), in: Capsule())
    }
}
