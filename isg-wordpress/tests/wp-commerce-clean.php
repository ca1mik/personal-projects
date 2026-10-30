<?php
/** Removes only local QA commerce data created by wp-commerce-fixture.php. */

$host = wp_parse_url(home_url(), PHP_URL_HOST);
if (!in_array($host, array('127.0.0.1', 'localhost'), true)) {
    WP_CLI::error('Cleanup is allowed only on a local WordPress installation.');
}
wp_set_current_user(1);
foreach (wc_get_orders(array('limit' => -1, 'billing_email' => 'qa@example.test')) as $order) {
    $order->delete(true);
}
foreach (array('isg-qa-download', 'isg-qa-options') as $slug) {
    $post = get_page_by_path($slug, OBJECT, 'product');
    if (!$post || $post->post_type !== 'product') { continue; }
    $product = wc_get_product($post->ID);
    if ($product instanceof WC_Product_Variable) {
        foreach ($product->get_children() as $child_id) {
            $child = wc_get_product($child_id);
            if ($child) { $child->delete(true); }
        }
    }
    $product->delete(true);
}
$uploads = wp_upload_dir();
$file = $uploads['basedir'] . '/isg-qa-download.png';
if (is_file($file)) { unlink($file); }
WP_CLI::success('Local QA orders and products were removed.');
