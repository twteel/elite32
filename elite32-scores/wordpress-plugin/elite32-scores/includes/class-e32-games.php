<?php
/**
 * Storage for games. One row per game in a dedicated table so score updates are
 * single atomic UPDATE statements (safe with several scorekeepers at once).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class E32_Games {

	const STATUSES = array( 'scheduled', 'live', 'final', 'postponed', 'canceled' );

	/** Fields a client may set when creating or editing a game. */
	const EDITABLE = array(
		'event_name',
		'division',
		'venue',
		'starts_at',
		'home_team',
		'away_team',
		'home_score',
		'away_score',
		'status',
		'period',
		'sort_order',
	);

	public static function table() {
		global $wpdb;
		return $wpdb->prefix . 'e32_games';
	}

	public static function install() {
		global $wpdb;
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';

		$table   = self::table();
		$charset = $wpdb->get_charset_collate();

		dbDelta(
			"CREATE TABLE {$table} (
				id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
				event_name varchar(191) NOT NULL DEFAULT '',
				division varchar(100) NOT NULL DEFAULT '',
				venue varchar(191) NOT NULL DEFAULT '',
				starts_at datetime NULL DEFAULT NULL,
				home_team varchar(191) NOT NULL DEFAULT '',
				away_team varchar(191) NOT NULL DEFAULT '',
				home_score int(11) NOT NULL DEFAULT 0,
				away_score int(11) NOT NULL DEFAULT 0,
				status varchar(20) NOT NULL DEFAULT 'scheduled',
				period varchar(40) NOT NULL DEFAULT '',
				sort_order int(11) NOT NULL DEFAULT 0,
				created_at datetime NOT NULL,
				updated_at datetime NOT NULL,
				PRIMARY KEY  (id),
				KEY starts_at (starts_at),
				KEY status (status),
				KEY updated_at (updated_at)
			) {$charset};"
		);

		update_option( 'e32_scores_db_version', E32_SCORES_DB_VERSION );
	}

	/**
	 * Monotonic counter bumped on every change. Clients can show "last updated"
	 * or skip re-rendering when it has not moved.
	 */
	public static function revision() {
		return (int) get_option( 'e32_scores_revision', 0 );
	}

	private static function bump_revision() {
		global $wpdb;
		// Increment in SQL so simultaneous scorekeepers never lose a bump.
		$bumped = $wpdb->query(
			"UPDATE {$wpdb->options} SET option_value = option_value + 1 WHERE option_name = 'e32_scores_revision'"
		);
		if ( ! $bumped ) {
			add_option( 'e32_scores_revision', 1, '', false );
		}
		wp_cache_delete( 'e32_scores_revision', 'options' );
	}

	private static function now_utc() {
		return gmdate( 'Y-m-d H:i:s' );
	}

	/**
	 * @param array $args {
	 *     @type string $status  Only games with this status.
	 *     @type string $event   Only games for this event name.
	 *     @type string $date    Y-m-d in the site's time zone.
	 *     @type bool   $all     Include old games too (admin views).
	 * }
	 */
	public static function query( array $args = array() ) {
		global $wpdb;
		$table  = self::table();
		$where  = array( '1=1' );
		$params = array();

		if ( ! empty( $args['status'] ) && in_array( $args['status'], self::STATUSES, true ) ) {
			$where[]  = 'status = %s';
			$params[] = $args['status'];
		}

		if ( ! empty( $args['event'] ) ) {
			$where[]  = 'event_name = %s';
			$params[] = $args['event'];
		}

		if ( ! empty( $args['date'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', $args['date'] ) ) {
			$tz    = wp_timezone();
			$start = new DateTime( $args['date'] . ' 00:00:00', $tz );
			$end   = ( clone $start )->modify( '+1 day' );
			$utc   = new DateTimeZone( 'UTC' );

			$where[]  = 'starts_at >= %s AND starts_at < %s';
			$params[] = $start->setTimezone( $utc )->format( 'Y-m-d H:i:s' );
			$params[] = $end->setTimezone( $utc )->format( 'Y-m-d H:i:s' );
		} elseif ( empty( $args['all'] ) ) {
			// Default window: live games, anything without a time, and the last 3 days onward.
			$where[]  = "(status = 'live' OR starts_at IS NULL OR starts_at >= %s)";
			$params[] = gmdate( 'Y-m-d H:i:s', time() - 3 * DAY_IN_SECONDS );
		}

		$sql = "SELECT * FROM {$table} WHERE " . implode( ' AND ', $where )
			. ' ORDER BY starts_at IS NULL, starts_at ASC, sort_order ASC, id ASC LIMIT 1000';

		$rows = $params ? $wpdb->get_results( $wpdb->prepare( $sql, $params ), ARRAY_A ) : $wpdb->get_results( $sql, ARRAY_A );

		return array_map( array( __CLASS__, 'format' ), $rows ?: array() );
	}

	public static function get( $id ) {
		global $wpdb;
		$row = $wpdb->get_row(
			$wpdb->prepare( 'SELECT * FROM ' . self::table() . ' WHERE id = %d', $id ),
			ARRAY_A
		);
		return $row ? self::format( $row ) : null;
	}

	/** @return array|WP_Error The created game. */
	public static function create( array $data ) {
		global $wpdb;

		$clean = self::sanitize( $data );
		if ( is_wp_error( $clean ) ) {
			return $clean;
		}
		if ( empty( $clean['home_team'] ) || empty( $clean['away_team'] ) ) {
			return new WP_Error( 'e32_missing_teams', 'Both home_team and away_team are required.', array( 'status' => 400 ) );
		}

		$now                 = self::now_utc();
		$clean['created_at'] = $now;
		$clean['updated_at'] = $now;

		if ( false === $wpdb->insert( self::table(), $clean ) ) {
			return new WP_Error( 'e32_db', 'Could not save the game.', array( 'status' => 500 ) );
		}

		self::bump_revision();
		return self::get( $wpdb->insert_id );
	}

	/** @return array|WP_Error|null The updated game, or null if it does not exist. */
	public static function update( $id, array $data ) {
		global $wpdb;

		if ( ! self::get( $id ) ) {
			return null;
		}

		$clean = self::sanitize( $data );
		if ( is_wp_error( $clean ) ) {
			return $clean;
		}

		$clean['updated_at'] = self::now_utc();
		$wpdb->update( self::table(), $clean, array( 'id' => (int) $id ) );

		self::bump_revision();
		return self::get( $id );
	}

	/**
	 * Add (or subtract) points atomically. Starting to score a scheduled game
	 * flips it to live automatically.
	 *
	 * @return array|null The updated game, or null if it does not exist.
	 */
	public static function add_points( $id, $side, $points ) {
		global $wpdb;

		$column = 'home' === $side ? 'home_score' : 'away_score';
		$table  = self::table();

		$updated = $wpdb->query(
			$wpdb->prepare(
				"UPDATE {$table}
				 SET {$column} = GREATEST(0, {$column} + %d),
				     status = IF(status = 'scheduled' AND %d > 0, 'live', status),
				     updated_at = %s
				 WHERE id = %d",
				(int) $points,
				(int) $points,
				self::now_utc(),
				(int) $id
			)
		);

		if ( ! $updated ) {
			return self::get( $id );
		}

		self::bump_revision();
		return self::get( $id );
	}

	public static function delete( $id ) {
		global $wpdb;
		$deleted = $wpdb->delete( self::table(), array( 'id' => (int) $id ) );
		if ( $deleted ) {
			self::bump_revision();
		}
		return (bool) $deleted;
	}

	/**
	 * Keep only known fields and coerce their types.
	 *
	 * @return array|WP_Error
	 */
	public static function sanitize( array $data ) {
		$out = array();

		foreach ( self::EDITABLE as $field ) {
			if ( ! array_key_exists( $field, $data ) ) {
				continue;
			}
			$value = $data[ $field ];

			switch ( $field ) {
				case 'home_score':
				case 'away_score':
					$out[ $field ] = max( 0, (int) $value );
					break;

				case 'sort_order':
					$out[ $field ] = (int) $value;
					break;

				case 'status':
					$value = strtolower( trim( (string) $value ) );
					if ( ! in_array( $value, self::STATUSES, true ) ) {
						return new WP_Error(
							'e32_bad_status',
							'status must be one of: ' . implode( ', ', self::STATUSES ),
							array( 'status' => 400 )
						);
					}
					$out[ $field ] = $value;
					break;

				case 'starts_at':
					$parsed = self::parse_datetime( $value );
					if ( is_wp_error( $parsed ) ) {
						return $parsed;
					}
					$out[ $field ] = $parsed;
					break;

				default:
					$out[ $field ] = sanitize_text_field( (string) $value );
			}
		}

		return $out;
	}

	/**
	 * Accepts ISO 8601 with an offset ("2026-04-04T10:00:00-04:00", "...Z") or a
	 * local time without one ("2026-04-04 10:00", "2026-04-04T10:00" from a
	 * datetime-local input), which is read in the site's time zone. Stored as UTC.
	 *
	 * @return string|null|WP_Error
	 */
	public static function parse_datetime( $value ) {
		$value = trim( (string) $value );
		if ( '' === $value ) {
			return null;
		}
		try {
			$dt = new DateTime( $value, wp_timezone() );
		} catch ( Exception $e ) {
			return new WP_Error( 'e32_bad_date', 'starts_at is not a valid date/time.', array( 'status' => 400 ) );
		}
		return $dt->setTimezone( new DateTimeZone( 'UTC' ) )->format( 'Y-m-d H:i:s' );
	}

	/** Shape a DB row for API output. */
	public static function format( array $row ) {
		$iso = function ( $mysql ) {
			return $mysql ? gmdate( 'Y-m-d\TH:i:s\Z', strtotime( $mysql . ' UTC' ) ) : null;
		};

		return array(
			'id'         => (int) $row['id'],
			'event_name' => $row['event_name'],
			'division'   => $row['division'],
			'venue'      => $row['venue'],
			'starts_at'  => $iso( $row['starts_at'] ),
			'home_team'  => $row['home_team'],
			'away_team'  => $row['away_team'],
			'home_score' => (int) $row['home_score'],
			'away_score' => (int) $row['away_score'],
			'status'     => $row['status'],
			'period'     => $row['period'],
			'sort_order' => (int) $row['sort_order'],
			'updated_at' => $iso( $row['updated_at'] ),
		);
	}
}
