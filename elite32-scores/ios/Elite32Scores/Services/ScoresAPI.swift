import Foundation

struct Credentials: Codable, Equatable {
    var username: String
    /// A WordPress Application Password (Users → Profile → Application Passwords),
    /// not the normal login password.
    var appPassword: String

    var authorizationHeader: String {
        let token = Data("\(username):\(appPassword.replacingOccurrences(of: " ", with: ""))".utf8)
        return "Basic \(token.base64EncodedString())"
    }
}

enum APIError: LocalizedError {
    case server(status: Int, message: String)
    case badResponse

    var errorDescription: String? {
        switch self {
        case .server(let status, let message):
            status == 401 ? "Sign-in failed. Check the username and Application Password." : message
        case .badResponse:
            "Unexpected response from the server."
        }
    }
}

/// Thin client for the Elite32 Live Scores WordPress plugin (/wp-json/elite32/v1).
struct ScoresAPI {
    var credentials: Credentials?

    private static let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        config.timeoutIntervalForRequest = 15
        return URLSession(configuration: config)
    }()

    func games(all: Bool = false) async throws -> GamesResponse {
        var items = [URLQueryItem(name: "_", value: String(Int(Date().timeIntervalSince1970)))]
        if all { items.append(URLQueryItem(name: "all", value: "1")) }
        return try await send("games", query: items)
    }

    func verifySignIn() async throws {
        struct Me: Decodable { let displayName: String }
        let _: Me = try await send("me")
    }

    func createGame(_ changes: GameChanges) async throws -> Game {
        try await send("games", method: "POST", body: try JSONEncoder.api.encode(changes))
    }

    func updateGame(id: Int, _ changes: GameChanges) async throws -> Game {
        try await send("games/\(id)", method: "PATCH", body: try JSONEncoder.api.encode(changes))
    }

    func addPoints(gameID: Int, side: Side, points: Int) async throws -> Game {
        struct Body: Encodable { let side: Side; let points: Int }
        let body = try JSONEncoder.api.encode(Body(side: side, points: points))
        return try await send("games/\(gameID)/points", method: "POST", body: body)
    }

    func deleteGame(id: Int) async throws {
        struct Deleted: Decodable { let deleted: Bool }
        let _: Deleted = try await send("games/\(id)", method: "DELETE")
    }

    // MARK: - Plumbing

    private struct WPError: Decodable { let message: String }

    private func send<T: Decodable>(
        _ path: String,
        method: String = "GET",
        query: [URLQueryItem] = [],
        body: Data? = nil
    ) async throws -> T {
        var url = Config.apiBase.appending(path: path)
        if !query.isEmpty { url.append(queryItems: query) }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let credentials {
            request.setValue(credentials.authorizationHeader, forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }

        let (data, response) = try await Self.session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.badResponse }

        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder.api.decode(WPError.self, from: data))?.message
                ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
            throw APIError.server(status: http.statusCode, message: message)
        }
        return try JSONDecoder.api.decode(T.self, from: data)
    }
}
