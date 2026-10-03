<?php
/**
 * REST API under /wp-json/elite32/v1.
 *
 * Public (no login):
 *   GET    /games            List games. Query: status, event, date (Y-m-d), all=1
 *   GET    /games/{id}       One game.
 *
 * Scorekeepers (user with the manage_e32_scores capability; the app signs in
 * with a WordPress Application Password over HTTPS):
 *   GET    /me               Check credentials.
 *   POST   /games            Create a game.
 *   PATCH  /games/{id}       Edit any field (score, status, period, teams...).
 *   POST   /games/{id}/points  { "side": "home"|"away", "points": 2 }  atomic add/subtract
 *   DELETE /games/{id}       Remove a game.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class E32_Rest {

	const NS = 'elite32/v1';

	public static function register_routes() {
		register_rest_route(
			self::NS,
			'/games',
			array(
				array(
					'methods'             => WP_REST_Server::READABLE,
					'callback'            => array( __CLASS__, 'list_games' ),
					'permission_callback' => '__return_true',
				),
				array(
					'methods'             => WP_REST_Server::CREATABLE,
					'callback'            => array( __CLASS__, 'create_game' ),
					'permission_callback' => array( __CLASS__, 'can_edit' ),
				),
			)
		);

		register_rest_route(
			self::NS,
			'/games/(?P<id>\d+)',
			array(
				array(
					'methods'             => WP_REST_Server::READABLE,
					'callback'            => array( __CLASS__, 'get_game' ),
					'permission_callback' => '__return_true',
				),
				array(
					'methods'             => WP_REST_Server::EDITABLE,
					'callback'            => array( __CLASS__, 'update_game' ),
					'permission_callback' => array( __CLASS__, 'can_edit' ),
				),
				array(
					'methods'             => WP_REST_Server::DELETABLE,
					'callback'            => array( __CLASS__, 'delete_game' ),
					'permission_callback' => array( __CLASS__, 'can_edit' ),
				),
			)
		);

		register_rest_route(
			self::NS,
			'/games/(?P<id>\d+)/points',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( __CLASS__, 'add_points' ),
				'permission_callback' => array( __CLASS__, 'can_edit' ),
				'args'                => array(
					'side'   => array(
						'required' => true,
						'enum'     => array( 'home', 'away' ),
					),
					'points' => array(
						'required' => true,
						'type'     => 'integer',
						'minimum'  => -10,
						'maximum'  => 10,
					),
				),
			)
		);

		register_rest_route(
			self::NS,
			'/me',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( __CLASS__, 'me' ),
				'permission_callback' => array( __CLASS__, 'can_edit' ),
			)
		);
	}

	public static function can_edit() {
		if ( current_user_can( E32_SCORES_CAP ) ) {
			return true;
		}
		return new WP_Error(
			'e32_forbidden',
			is_user_logged_in()
				? 'This account is not allowed to update scores.'
				: 'Sign in with a WordPress username and Application Password.',
			array( 'status' => is_user_logged_in() ? 403 : 401 )
		);
	}

	/**
	 * Scores change constantly, so make sure no page cache (Varnish on Cloudways,
	 * Breeze, Cloudflare...) holds on to a stale copy.
	 */
	private static function respond( $data, $status = 200 ) {
		$response = new WP_REST_Response( $data, $status );
		$response->header( 'Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0' );
		$response->header( 'Pragma', 'no-cache' );
		$response->header( 'X-E32-Revision', (string) E32_Games::revision() );
		return $response;
	}

	private static function not_found() {
		return new WP_Error( 'e32_not_found', 'Game not found.', array( 'status' => 404 ) );
	}

	public static function list_games( WP_REST_Request $request ) {
		$games = E32_Games::query(
			array(
				'status' => $request->get_param( 'status' ),
				'event'  => $request->get_param( 'event' ),
				'date'   => $request->get_param( 'date' ),
				'all'    => (bool) $request->get_param( 'all' ),
			)
		);

		return self::respond(
			array(
				'revision'    => E32_Games::revision(),
				'server_time' => gmdate( 'Y-m-d\TH:i:s\Z' ),
				'games'       => $games,
			)
		);
	}

	public static function get_game( WP_REST_Request $request ) {
		$game = E32_Games::get( (int) $request['id'] );
		return $game ? self::respond( $game ) : self::not_found();
	}

	public static function create_game( WP_REST_Request $request ) {
		$game = E32_Games::create( self::body( $request ) );
		return is_wp_error( $game ) ? $game : self::respond( $game, 201 );
	}

	public static function update_game( WP_REST_Request $request ) {
		$game = E32_Games::update( (int) $request['id'], self::body( $request ) );
		if ( null === $game ) {
			return self::not_found();
		}
		return is_wp_error( $game ) ? $game : self::respond( $game );
	}

	public static function add_points( WP_REST_Request $request ) {
		$game = E32_Games::add_points(
			(int) $request['id'],
			$request->get_param( 'side' ),
			(int) $request->get_param( 'points' )
		);
		return $game ? self::respond( $game ) : self::not_found();
	}

	public static function delete_game( WP_REST_Request $request ) {
		return E32_Games::delete( (int) $request['id'] )
			? self::respond( array( 'deleted' => true ) )
			: self::not_found();
	}

	public static function me() {
		$user = wp_get_current_user();
		return self::respond(
			array(
				'id'           => $user->ID,
				'display_name' => $user->display_name,
			)
		);
	}

	private static function body( WP_REST_Request $request ) {
		$json = $request->get_json_params();
		return is_array( $json ) ? $json : $request->get_body_params();
	}
}
