<?php
/**
 * wp-admin → "Elite32 Scores": a phone-friendly scorekeeper screen.
 * The page is a shell; assets/admin.js drives it through the REST API.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class E32_Admin {

	const SLUG = 'elite32-scores';

	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_enqueue_scripts', array( __CLASS__, 'assets' ) );
	}

	public static function menu() {
		add_menu_page(
			'Elite32 Scores',
			'Elite32 Scores',
			E32_SCORES_CAP,
			self::SLUG,
			array( __CLASS__, 'render' ),
			'dashicons-awards',
			3
		);
	}

	public static function assets( $hook ) {
		if ( 'toplevel_page_' . self::SLUG !== $hook ) {
			return;
		}
		wp_enqueue_style( 'e32-scores-admin', E32_SCORES_URL . 'assets/admin.css', array(), E32_SCORES_VERSION );
		wp_enqueue_script( 'e32-scores-admin', E32_SCORES_URL . 'assets/admin.js', array(), E32_SCORES_VERSION, true );
		wp_localize_script(
			'e32-scores-admin',
			'E32Scores',
			array(
				'root'     => esc_url_raw( rest_url( E32_Rest::NS ) ),
				'nonce'    => wp_create_nonce( 'wp_rest' ),
				'statuses' => E32_Games::STATUSES,
				'timezone' => wp_timezone_string(),
			)
		);
	}

	public static function render() {
		?>
		<div class="wrap e32a">
			<h1 class="e32a-title">Elite32 Scores</h1>
			<p class="e32a-sub">
				Changes go live instantly in the iPhone app and on the site.
				Times are in <strong><?php echo esc_html( wp_timezone_string() ); ?></strong>.
			</p>

			<div class="e32a-toolbar">
				<label>Day <input type="date" id="e32a-date"></label>
				<label><input type="checkbox" id="e32a-all"> Show all days</label>
				<button type="button" class="button" id="e32a-refresh">Refresh</button>
				<span class="e32a-status" id="e32a-status" aria-live="polite"></span>
			</div>

			<div id="e32a-games" class="e32a-games"></div>

			<details class="e32a-panel" id="e32a-add">
				<summary>+ Add a game</summary>
				<form id="e32a-add-form" class="e32a-form">
					<label>Event <input name="event_name" list="e32a-events" placeholder="Middle School Madness"></label>
					<label>Division <input name="division" placeholder="8th Grade Boys"></label>
					<label>Court / venue <input name="venue" placeholder="Court 1 – South Shore HS"></label>
					<label>Start <input name="starts_at" type="datetime-local"></label>
					<label>Home team <input name="home_team" required></label>
					<label>Away team <input name="away_team" required></label>
					<button class="button button-primary" type="submit">Add game</button>
				</form>
				<datalist id="e32a-events"></datalist>
			</details>

			<details class="e32a-panel">
				<summary>Paste a whole schedule</summary>
				<p>One game per line: <code>2026-04-04 10:00 | Event | Division | Court | Home | Away</code></p>
				<textarea id="e32a-bulk" rows="8" placeholder="2026-04-04 10:00 | Middle School Madness | 8th Grade Boys | Court 1 | Team A | Team B"></textarea>
				<p><button type="button" class="button button-primary" id="e32a-bulk-go">Import games</button></p>
			</details>
		</div>
		<?php
	}
}
