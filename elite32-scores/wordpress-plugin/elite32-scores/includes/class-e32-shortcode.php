<?php
/**
 * [elite32_scores] — live scoreboard on any page of the website.
 * Optional attributes: event="Middle School Madness" status="live" refresh="20"
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class E32_Shortcode {

	public static function init() {
		add_shortcode( 'elite32_scores', array( __CLASS__, 'render' ) );
	}

	public static function render( $atts ) {
		$atts = shortcode_atts(
			array(
				'event'   => '',
				'status'  => '',
				'refresh' => 20,
			),
			$atts,
			'elite32_scores'
		);

		wp_enqueue_style( 'e32-scores-board', E32_SCORES_URL . 'assets/board.css', array(), E32_SCORES_VERSION );
		wp_enqueue_script( 'e32-scores-board', E32_SCORES_URL . 'assets/board.js', array(), E32_SCORES_VERSION, true );

		$query = array_filter(
			array(
				'event'  => $atts['event'],
				'status' => $atts['status'],
			)
		);
		$src   = add_query_arg( $query, rest_url( E32_Rest::NS . '/games' ) );

		// The board renders client-side so page caches never freeze the scores.
		return sprintf(
			'<div class="e32b" data-src="%s" data-refresh="%d"><p class="e32b-loading">Loading scores…</p></div>',
			esc_url( $src ),
			max( 5, (int) $atts['refresh'] )
		);
	}
}
