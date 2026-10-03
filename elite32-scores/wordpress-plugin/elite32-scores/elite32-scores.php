<?php
/**
 * Plugin Name: Elite32 Live Scores
 * Description: Live game scores for Elite 32 events. Powers the Elite32 iPhone app, a mobile-friendly scorekeeper screen in wp-admin, and the [elite32_scores] shortcode.
 * Version:     1.0.0
 * Author:      Elite 32
 * Requires PHP: 7.4
 * Requires at least: 5.6
 * License:     GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'E32_SCORES_VERSION', '1.0.0' );
define( 'E32_SCORES_DB_VERSION', '1' );
define( 'E32_SCORES_FILE', __FILE__ );
define( 'E32_SCORES_DIR', plugin_dir_path( __FILE__ ) );
define( 'E32_SCORES_URL', plugin_dir_url( __FILE__ ) );

// Capability required to change scores. Granted to administrators and editors on activation.
define( 'E32_SCORES_CAP', 'manage_e32_scores' );

require_once E32_SCORES_DIR . 'includes/class-e32-games.php';
require_once E32_SCORES_DIR . 'includes/class-e32-rest.php';
require_once E32_SCORES_DIR . 'includes/class-e32-admin.php';
require_once E32_SCORES_DIR . 'includes/class-e32-shortcode.php';

register_activation_hook( __FILE__, 'e32_scores_activate' );

function e32_scores_activate() {
	E32_Games::install();

	foreach ( array( 'administrator', 'editor' ) as $role_name ) {
		$role = get_role( $role_name );
		if ( $role ) {
			$role->add_cap( E32_SCORES_CAP );
		}
	}
}

add_action( 'plugins_loaded', function () {
	if ( get_option( 'e32_scores_db_version' ) !== E32_SCORES_DB_VERSION ) {
		E32_Games::install();
	}
} );

add_action( 'rest_api_init', array( 'E32_Rest', 'register_routes' ) );

if ( is_admin() ) {
	E32_Admin::init();
}

E32_Shortcode::init();
