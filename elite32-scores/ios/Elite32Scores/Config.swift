import Foundation

enum Config {
    /// The WordPress site running the "Elite32 Live Scores" plugin.
    /// Change this when the site moves to its real domain (e.g. https://elite32.com).
    static let siteURL = URL(string: "https://wordpress-1586993-6595324.cloudwaysapps.com")!

    /// How often the app re-checks scores while it is open.
    static let refreshInterval: Duration = .seconds(15)

    static var apiBase: URL {
        siteURL.appending(path: "wp-json/elite32/v1")
    }
}
