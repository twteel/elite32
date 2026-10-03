import Foundation
import Observation

/// App-wide state: the latest games from the server, refreshed on a timer while
/// the app is open, plus the scorekeeper's sign-in.
@MainActor
@Observable
final class ScoreStore {
    private(set) var games: [Game] = []
    private(set) var lastUpdated: Date?
    private(set) var isLoading = false
    var errorMessage: String?

    private(set) var credentials: Credentials? = Keychain.load()
    var isScorekeeper: Bool { credentials != nil }

    private var api: ScoresAPI { ScoresAPI(credentials: credentials) }
    @ObservationIgnored private var pollTask: Task<Void, Never>?
    /// While a score change is on its way, ignore poll results that may predate it.
    @ObservationIgnored private var pendingWrites = 0

    // MARK: - Reading scores

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response = try await ScoresAPI().games()
            guard pendingWrites == 0 else { return }
            games = response.games
            lastUpdated = .now
            errorMessage = nil
        } catch is CancellationError {
            // App went to the background mid-request.
        } catch let error as URLError where error.code == .cancelled {
            // Same as above.
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func startPolling() {
        guard pollTask == nil else { return }
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: Config.refreshInterval)
            }
        }
    }

    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    func game(id: Int) -> Game? {
        games.first { $0.id == id }
    }

    // MARK: - Scorekeeping

    func signIn(username: String, appPassword: String) async throws {
        let candidate = Credentials(
            username: username.trimmingCharacters(in: .whitespaces),
            appPassword: appPassword.trimmingCharacters(in: .whitespaces)
        )
        try await ScoresAPI(credentials: candidate).verifySignIn()
        Keychain.save(candidate)
        credentials = candidate
    }

    func signOut() {
        Keychain.delete()
        credentials = nil
    }

    func addPoints(_ points: Int, to side: Side, in game: Game) async {
        // Show the new score immediately; the server's answer replaces it.
        apply(optimistic: game) { g in
            if side == .home { g.homeScore = max(0, g.homeScore + points) } else { g.awayScore = max(0, g.awayScore + points) }
            if g.status == .scheduled, points > 0 { g.status = .live }
        }
        await perform { try await $0.addPoints(gameID: game.id, side: side, points: points) }
    }

    func update(_ game: Game, _ changes: GameChanges) async {
        await perform { try await $0.updateGame(id: game.id, changes) }
    }

    @discardableResult
    func create(_ changes: GameChanges) async -> Bool {
        do {
            let created = try await api.createGame(changes)
            replace(created)
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func delete(_ game: Game) async {
        do {
            try await api.deleteGame(id: game.id)
            games.removeAll { $0.id == game.id }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func perform(_ call: (ScoresAPI) async throws -> Game) async {
        pendingWrites += 1
        defer { pendingWrites -= 1 }
        do {
            replace(try await call(api))
        } catch {
            errorMessage = error.localizedDescription
            pendingWrites -= 1
            await refresh() // put back the real score
            pendingWrites += 1
        }
    }

    private func apply(optimistic game: Game, _ change: (inout Game) -> Void) {
        guard let index = games.firstIndex(where: { $0.id == game.id }) else { return }
        change(&games[index])
    }

    private func replace(_ game: Game) {
        if let index = games.firstIndex(where: { $0.id == game.id }) {
            games[index] = game
        } else {
            games.append(game)
            games.sort { ($0.startsAt ?? .distantFuture) < ($1.startsAt ?? .distantFuture) }
        }
        lastUpdated = .now
    }
}
