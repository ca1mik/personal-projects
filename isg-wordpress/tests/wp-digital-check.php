<?php
/** Confirms that a paid local QA order grants a downloadable file. */

$orders = wc_get_orders(array('limit' => 1, 'orderby' => 'date', 'order' => 'DESC', 'billing_email' => 'qa@example.test'));
if (!$orders) {
    WP_CLI::error('No local QA order was found.');
}
$order = $orders[0];
$order->update_status('completed', 'Local fulfillment test.');
$downloads = $order->get_downloadable_items();
if (count($downloads) !== 1 || !$downloads[0]['download_url']) {
    WP_CLI::error('The completed order has no downloadable permission.');
}
$response = wp_remote_get($downloads[0]['download_url'], array('timeout' => 15));
WP_CLI::log($downloads[0]['download_url']);
WP_CLI::log(is_wp_error($response) ? $response->get_error_message() : 'HTTP ' . wp_remote_retrieve_response_code($response) . ' bytes=' . strlen(wp_remote_retrieve_body($response)));
if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200 || strlen(wp_remote_retrieve_body($response)) < 1000) {
    WP_CLI::error('The granted download did not return the file.');
}
WP_CLI::success('Order ' . $order->get_id() . ' grants ' . $downloads[0]['download_name'] . '.');
