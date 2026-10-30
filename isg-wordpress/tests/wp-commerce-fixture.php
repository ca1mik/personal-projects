<?php
/** Local WooCommerce fixture. Run with wp eval-file and never import into production. */

if (!class_exists('WC_Product_Simple')) {
    WP_CLI::error('WooCommerce is inactive.');
}
wp_set_current_user(1);

$existing = get_page_by_path('isg-qa-download', OBJECT, 'product');
$product = $existing ? wc_get_product($existing->ID) : new WC_Product_Simple();
$product->set_name('ISG QA download (local test only)');
$product->set_slug('isg-qa-download');
$product->set_status('publish');
$product->set_catalog_visibility('visible');
$product->set_regular_price('9.99');
$product->set_virtual(true);
$product->set_downloadable(true);
$uploads = wp_upload_dir();
$filename = $uploads['basedir'] . '/isg-qa-download.png';
if (!file_exists($filename)) {
    copy(get_template_directory() . '/assets/logo.png', $filename);
}
$directory = wc_get_container()->get(Automattic\WooCommerce\Internal\ProductDownloads\ApprovedDirectories\Register::class);
$approved_url = $uploads['baseurl'] . '/';
$directory_id = $directory->add_approved_directory($approved_url, true);
$directory->update_approved_directory($directory_id, $approved_url, true);
$download = new WC_Product_Download();
$download->set_id(md5('isg-local-qa-download'));
$download->set_name('QA file');
$download->set_file($uploads['baseurl'] . '/isg-qa-download.png');
WP_CLI::log('mode=' . $directory->get_mode() . ' approved=' . ($directory->is_valid_path($download->get_file()) ? 'yes' : 'no') . ' exists=' . ($download->file_exists() ? 'yes' : 'no') . ' type=' . $download->get_type_of_file_path() . ' allowed=' . ($download->is_allowed_filetype() ? 'yes' : 'no'));
$product->set_downloads(array($download));
$id = $product->save();

$settings = get_option('woocommerce_bacs_settings', array());
$settings['enabled'] = 'yes';
update_option('woocommerce_bacs_settings', $settings);
WP_CLI::success('Local test product ' . $id . ' is ready.');

$variable_post = get_page_by_path('isg-qa-options', OBJECT, 'product');
$variable = $variable_post ? wc_get_product($variable_post->ID) : new WC_Product_Variable();
$variable->set_name('ISG QA options (local test only)');
$variable->set_slug('isg-qa-options');
$variable->set_status('publish');
$variable->set_catalog_visibility('visible');
$variable->set_virtual(true);
$attribute = new WC_Product_Attribute();
$attribute->set_name('License');
$attribute->set_options(array('Standard', 'Extended'));
$attribute->set_visible(true);
$attribute->set_variation(true);
$variable->set_attributes(array($attribute));
$variable_id = $variable->save();
foreach (array('Standard' => '9.99', 'Extended' => '19.99') as $option => $price) {
    $variations = wc_get_products(array('type' => 'variation', 'parent' => $variable_id, 'limit' => -1));
    $matching = array_filter($variations, static fn($item) => $item->get_attribute('License') === $option);
    $variation = $matching ? reset($matching) : new WC_Product_Variation();
    $variation->set_parent_id($variable_id);
    $variation->set_attributes(array('license' => $option));
    $variation->set_regular_price($price);
    $variation->set_virtual(true);
    $variation->set_status('publish');
    $variation->save();
}
WP_CLI::success('Local option prices are ready.');
