import Foundation

enum GameStatus: String, Codable, CaseIterable, Identifiable {
    case scheduled, live, final, postponed, canceled

    var id: String { rawValue }

    var label: String {
        switch self {
        case .scheduled: "Scheduled"
        case .live: "Live"
        case .final: "Final"
        case .postponed: "Postponed"
        case .canceled: "Canceled"
        }
    }
}

struct Game: Codable, Identifiable, Hashable {
    let id: Int
    var eventName: String
    var division: String
    var venue: String
    var startsAt: Date?
    var homeTeam: String
    var awayTeam: String
    var homeScore: Int
    var awayScore: Int
    var status: GameStatus
    var period: String
    var sortOrder: Int
    var updatedAt: Date?

    var hasScore: Bool { status != .scheduled }

    var winner: Side? {
        guard status == .final, homeScore != awayScore else { return nil }
        return homeScore > awayScore ? .home : .away
    }

    var subtitle: String {
        [division, venue].filter { !$0.isEmpty }.joined(separator: " · ")
    }
}

enum Side: String, Codable {
    case home, away
}

struct GamesResponse: Codable {
    let revision: Int
    let serverTime: Date
    let games: [Game]
}

/// Fields sent when creating or editing a game. Nil fields are left unchanged.
struct GameChanges: Encodable {
    var eventName: String?
    var division: String?
    var venue: String?
    var startsAt: Date?
    var homeTeam: String?
    var awayTeam: String?
    var homeScore: Int?
    var awayScore: Int?
    var status: GameStatus?
    var period: String?
}

extension JSONDecoder {
    static let api: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .iso8601
        return d
    }()
}

extension JSONEncoder {
    static let api: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.dateEncodingStrategy = .iso8601
        return e
    }()
}
