import SwiftUI

/// The "update from anywhere" side of the app. Sign in once with a WordPress
/// Application Password, then tap +1 / +2 / +3 courtside.
struct ScorekeeperView: View {
    @Environment(ScoreStore.self) private var store
    @State private var showingAdd = false

    private var games: [Game] {
        // Live first, then upcoming, then finished.
        let rank: [GameStatus: Int] = [.live: 0, .scheduled: 1, .postponed: 2, .final: 3, .canceled: 4]
        return store.games.enumerated()
            .sorted { (rank[$0.element.status]!, $0.offset) < (rank[$1.element.status]!, $1.offset) }
            .map(\.element)
    }

    var body: some View {
        NavigationStack {
            Group {
                if store.isScorekeeper {
                    List {
                        if let message = store.errorMessage {
                            Label(message, systemImage: "exclamationmark.triangle")
                                .font(.footnote)
                                .foregroundStyle(.orange)
                        }
                        ForEach(games) { game in
                            NavigationLink(value: game.id) {
                                GameRow(game: game)
                            }
                            .listRowBackground(Color.e32Card)
                        }
                    }
                    .overlay {
                        if games.isEmpty {
                            ContentUnavailableView {
                                Label("No games yet", systemImage: "basketball")
                            } description: {
                                Text("Add today's games here, or paste a whole schedule in WordPress → Elite32 Scores.")
                            } actions: {
                                Button("Add a game") { showingAdd = true }
                            }
                        }
                    }
                    .refreshable { await store.refresh() }
                    .navigationDestination(for: Int.self) { KeepScoreView(gameID: $0) }
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button { showingAdd = true } label: { Label("Add game", systemImage: "plus") }
                        }
                        ToolbarItem(placement: .topBarLeading) {
                            Button("Sign out", role: .destructive) { store.signOut() }
                        }
                    }
                    .sheet(isPresented: $showingAdd) { EditGameView(game: nil) }
                } else {
                    SignInView()
                }
            }
            .navigationTitle("Scorekeeper")
        }
    }
}

struct SignInView: View {
    @Environment(ScoreStore.self) private var store
    @State private var username = ""
    @State private var appPassword = ""
    @State private var isWorking = false
    @State private var error: String?

    var body: some View {
        Form {
            Section {
                TextField("WordPress username", text: $username)
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Application Password", text: $appPassword)
                    .textContentType(.password)
            } header: {
                Text("Sign in to update scores")
            } footer: {
                Text("In WordPress go to Users → Profile → Application Passwords, name it “iPhone”, and paste the password it gives you here. Fans don't need to sign in — this is only for staff.")
            }

            if let error {
                Text(error).foregroundStyle(.red).font(.footnote)
            }

            Button {
                Task {
                    isWorking = true
                    defer { isWorking = false }
                    do {
                        try await store.signIn(username: username, appPassword: appPassword)
                    } catch {
                        self.error = error.localizedDescription
                    }
                }
            } label: {
                HStack {
                    Text("Sign in")
                    if isWorking { Spacer(); ProgressView() }
                }
            }
            .disabled(username.isEmpty || appPassword.isEmpty || isWorking)
        }
    }
}

struct KeepScoreView: View {
    @Environment(ScoreStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let gameID: Int

    @State private var editing = false
    @State private var confirmDelete = false
    @State private var customPeriod = ""

    private let periods = ["Q1", "Q2", "Q3", "Q4", "1st Half", "2nd Half", "OT", "2OT"]

    var body: some View {
        if let game = store.game(id: gameID) {
            ScrollView {
                VStack(spacing: 20) {
                    Text([game.eventName, game.division, game.venue].filter { !$0.isEmpty }.joined(separator: " · "))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)

                    ScorePad(game: game, side: .away)
                    ScorePad(game: game, side: .home)

                    Picker("Status", selection: Binding(
                        get: { game.status },
                        set: { status in Task { await store.update(game, GameChanges(status: status)) } }
                    )) {
                        Text("Scheduled").tag(GameStatus.scheduled)
                        Text("Live").tag(GameStatus.live)
                        Text("Final").tag(GameStatus.final)
                    }
                    .pickerStyle(.segmented)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("PERIOD").font(.caption.weight(.bold)).tracking(1.5).foregroundStyle(.secondary)
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 8) {
                            ForEach(periods, id: \.self) { period in
                                Button(period) {
                                    Task { await store.update(game, GameChanges(status: game.status == .scheduled ? .live : nil, period: period)) }
                                }
                                .buttonStyle(.bordered)
                                .tint(game.period == period ? Color.e32Pink : Color.gray)
                            }
                        }
                        HStack {
                            TextField("Other (e.g. Halftime)", text: $customPeriod)
                                .textFieldStyle(.roundedBorder)
                            Button("Set") {
                                let period = customPeriod
                                customPeriod = ""
                                Task { await store.update(game, GameChanges(period: period)) }
                            }
                            .disabled(customPeriod.isEmpty)
                        }
                    }

                    if let message = store.errorMessage {
                        Label(message, systemImage: "exclamationmark.triangle")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }

                    Button("Delete game", role: .destructive) { confirmDelete = true }
                        .padding(.top, 12)
                }
                .padding()
            }
            .navigationTitle("\(game.awayTeam) @ \(game.homeTeam)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                Button("Edit") { editing = true }
            }
            .sheet(isPresented: $editing) { EditGameView(game: game) }
            .confirmationDialog("Delete this game?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete", role: .destructive) {
                    Task {
                        await store.delete(game)
                        dismiss()
                    }
                }
            }
        } else {
            ContentUnavailableView("Game removed", systemImage: "xmark.circle")
        }
    }
}

/// One team's score with big tap targets.
private struct ScorePad: View {
    @Environment(ScoreStore.self) private var store
    let game: Game
    let side: Side

    private var team: String { side == .home ? game.homeTeam : game.awayTeam }
    private var score: Int { side == .home ? game.homeScore : game.awayScore }

    var body: some View {
        VStack(spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(side == .home ? "HOME" : "AWAY")
                        .font(.caption2.weight(.bold)).tracking(2).foregroundStyle(.secondary)
                    Text(team).font(.title3.weight(.bold)).lineLimit(2)
                }
                Spacer()
                Text("\(score)")
                    .font(.system(size: 56, weight: .heavy))
                    .monospacedDigit()
                    .contentTransition(.numericText(value: Double(score)))
                    .animation(.snappy, value: score)
            }

            HStack(spacing: 10) {
                ForEach([-1, 1, 2, 3], id: \.self) { points in
                    Button {
                        Task { await store.addPoints(points, to: side, in: game) }
                    } label: {
                        Text(points > 0 ? "+\(points)" : "\(points)")
                            .font(.title2.weight(.heavy))
                            .frame(maxWidth: .infinity, minHeight: 56)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(points > 0 ? Color.e32Pink : Color(white: 0.25))
                }
            }
        }
        .padding()
        .background(Color.e32Card, in: RoundedRectangle(cornerRadius: 18))
        .sensoryFeedback(.impact(weight: .medium), trigger: score)
    }
}

/// Add a new game (game == nil) or edit an existing one.
struct EditGameView: View {
    @Environment(ScoreStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let game: Game?

    @State private var eventName = ""
    @State private var division = ""
    @State private var venue = ""
    @State private var homeTeam = ""
    @State private var awayTeam = ""
    @State private var hasStart = true
    @State private var startsAt = Date()
    @State private var homeScore = 0
    @State private var awayScore = 0
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Teams") {
                    TextField("Away team", text: $awayTeam)
                    TextField("Home team", text: $homeTeam)
                }
                Section("Details") {
                    TextField("Event (e.g. Middle School Madness)", text: $eventName)
                    TextField("Division (e.g. 8th Grade Boys)", text: $division)
                    TextField("Court / venue", text: $venue)
                    Toggle("Start time", isOn: $hasStart)
                    if hasStart {
                        DatePicker("Starts", selection: $startsAt)
                    }
                }
                if game != nil {
                    Section("Fix the score") {
                        Stepper("Away: \(awayScore)", value: $awayScore, in: 0...300)
                        Stepper("Home: \(homeScore)", value: $homeScore, in: 0...300)
                    }
                }
            }
            .navigationTitle(game == nil ? "Add game" : "Edit game")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(homeTeam.isEmpty || awayTeam.isEmpty || isSaving)
                }
            }
            .onAppear(perform: load)
        }
    }

    private func load() {
        guard let game else {
            // New games default to the event most recently used.
            eventName = store.games.last?.eventName ?? ""
            return
        }
        eventName = game.eventName
        division = game.division
        venue = game.venue
        homeTeam = game.homeTeam
        awayTeam = game.awayTeam
        hasStart = game.startsAt != nil
        startsAt = game.startsAt ?? Date()
        homeScore = game.homeScore
        awayScore = game.awayScore
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }

        var changes = GameChanges(
            eventName: eventName,
            division: division,
            venue: venue,
            startsAt: hasStart ? startsAt : nil,
            homeTeam: homeTeam,
            awayTeam: awayTeam
        )
        if let game {
            changes.homeScore = homeScore
            changes.awayScore = awayScore
            await store.update(game, changes)
            dismiss()
        } else if await store.create(changes) {
            dismiss()
        }
    }
}
