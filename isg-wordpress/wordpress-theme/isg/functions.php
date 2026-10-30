<?php
/** Theme setup and content model. */

if (!defined('ABSPATH')) {
    exit;
}
require_once get_template_directory() . '/inc/starter.php';

function isg_setup(): void {
    load_theme_textdomain('isg', get_template_directory() . '/languages');
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');
    add_theme_support('custom-logo', array('height' => 80, 'width' => 80, 'flex-height' => true, 'flex-width' => true));
    add_theme_support('html5', array('search-form', 'comment-form', 'comment-list', 'gallery', 'caption', 'style', 'script'));
    add_theme_support('responsive-embeds');
    add_theme_support('align-wide');
    add_theme_support('editor-styles');
    add_theme_support('woocommerce');
    add_theme_support('wc-product-gallery-zoom');
    add_theme_support('wc-product-gallery-lightbox');
    add_theme_support('wc-product-gallery-slider');
    register_nav_menus(array('primary' => __('Primary navigation', 'isg'), 'footer' => __('Footer navigation', 'isg')));
    add_image_size('isg-card', 720, 480, true);
}
add_action('after_setup_theme', 'isg_setup');

function isg_assets(): void {
    $version = wp_get_theme()->get('Version');
    wp_enqueue_style('isg-site', get_template_directory_uri() . '/assets/site.css', array(), $version);
    wp_enqueue_style('isg-wordpress', get_template_directory_uri() . '/assets/wordpress.css', array('isg-site'), $version);
    wp_enqueue_script('isg-theme', get_template_directory_uri() . '/assets/theme.js', array(), $version, true);
}
add_action('wp_enqueue_scripts', 'isg_assets');

function isg_meta_description(): void {
    if (defined('WPSEO_VERSION') || defined('RANK_MATH_VERSION') || defined('AIOSEO_VERSION')) { return; }
    $description = '';
    if (is_front_page()) {
        $description = get_theme_mod('isg_tagline', 'Software, self-service devices and connected systems. Innovation for life.');
    } elseif (is_singular()) {
        $post = get_queried_object();
        if ($post instanceof WP_Post) {
            $description = $post->post_excerpt ?: wp_trim_words(wp_strip_all_tags($post->post_content), 26, '');
        }
    } elseif (is_tax()) {
        $description = term_description();
    }
    $description = trim(wp_strip_all_tags($description));
    if ($description) {
        echo '<meta name="description" content="' . esc_attr(mb_substr($description, 0, 160)) . '">' . "\n";
    }
}
add_action('wp_head', 'isg_meta_description', 5);

function isg_register_content(): void {
    $types = array(
        'isg_product' => array('Products', 'Product', 'products', 'dashicons-screenoptions'),
        'isg_service' => array('Services', 'Service', 'services', 'dashicons-admin-tools'),
        'isg_download' => array('Downloads', 'Download', 'downloads', 'dashicons-download'),
        'isg_case' => array('Implementations', 'Implementation', 'implementations', 'dashicons-portfolio'),
        'isg_partner' => array('Partners', 'Partner', 'partners', 'dashicons-groups'),
        'isg_job' => array('Vacancies', 'Vacancy', 'careers', 'dashicons-businessperson'),
        'isg_video' => array('Videos', 'Video', 'videos', 'dashicons-video-alt3'),
        'isg_slide' => array('Hero slides', 'Hero slide', 'hero-slides', 'dashicons-images-alt2'),
    );
    foreach ($types as $type => $data) {
        register_post_type($type, array(
            'labels' => array('name' => __($data[0], 'isg'), 'singular_name' => __($data[1], 'isg')),
            'public' => $type !== 'isg_slide',
            'show_ui' => true,
            'show_in_rest' => true,
            'has_archive' => $type !== 'isg_slide',
            'rewrite' => array('slug' => $data[2], 'with_front' => false),
            'menu_icon' => $data[3],
            'supports' => array('title', 'editor', 'excerpt', 'thumbnail', 'revisions', 'page-attributes'),
        ));
    }
    register_taxonomy('isg_product_type', 'isg_product', array(
        'labels' => array('name' => __('Product types', 'isg')),
        'hierarchical' => true, 'show_in_rest' => true, 'show_admin_column' => true,
        'rewrite' => array('slug' => 'product-type', 'with_front' => false),
    ));
    register_taxonomy('isg_service_group', 'isg_service', array(
        'labels' => array('name' => __('Service groups', 'isg')),
        'hierarchical' => true, 'show_in_rest' => true, 'show_admin_column' => true,
        'rewrite' => array('slug' => 'service-group', 'with_front' => false),
    ));
    register_taxonomy('isg_industry', array('isg_product', 'isg_service', 'isg_case'), array(
        'labels' => array('name' => __('Industries', 'isg')),
        'hierarchical' => true, 'show_in_rest' => true, 'show_admin_column' => true,
        'rewrite' => array('slug' => 'industries', 'with_front' => false),
    ));
    register_taxonomy('isg_download_project', 'isg_download', array(
        'labels' => array('name' => __('Projects', 'isg')),
        'hierarchical' => true, 'show_in_rest' => true, 'show_admin_column' => true,
        'rewrite' => array('slug' => 'download-project', 'with_front' => false),
    ));
}
add_action('init', 'isg_register_content');

function isg_register_meta(): void {
    register_term_meta('isg_download_project', 'isg_color', array(
        'show_in_rest' => true, 'single' => true, 'type' => 'string',
        'sanitize_callback' => 'sanitize_hex_color',
        'auth_callback' => static function (): bool { return current_user_can('manage_categories'); },
    ));
    foreach (array('isg_download', 'isg_slide', 'isg_product', 'isg_service', 'isg_video') as $type) {
        register_post_meta($type, '_isg_external_url', array(
            'show_in_rest' => true, 'single' => true, 'type' => 'string',
            'sanitize_callback' => 'esc_url_raw',
            'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
        ));
    }
    foreach (array('_isg_file_size', '_isg_file_type') as $key) {
        register_post_meta('isg_download', $key, array(
            'show_in_rest' => true, 'single' => true, 'type' => 'string',
            'sanitize_callback' => 'sanitize_text_field',
            'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
        ));
    }
    register_post_meta('isg_slide', '_isg_video_url', array(
        'show_in_rest' => true, 'single' => true, 'type' => 'string',
        'sanitize_callback' => 'esc_url_raw',
        'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
    ));
    register_post_meta('isg_video', '_isg_duration', array(
        'show_in_rest' => true, 'single' => true, 'type' => 'string',
        'sanitize_callback' => 'sanitize_text_field',
        'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
    ));
    foreach (array('isg_download', 'isg_case') as $type) {
        register_post_meta($type, '_isg_related_product', array(
            'show_in_rest' => true, 'single' => true, 'type' => 'integer',
            'sanitize_callback' => 'absint',
            'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
        ));
    }
    register_post_meta('isg_product', '_isg_shop_product_id', array(
        'show_in_rest' => true, 'single' => true, 'type' => 'integer',
        'sanitize_callback' => 'absint',
        'auth_callback' => static function (): bool { return current_user_can('edit_posts'); },
    ));
}
add_action('init', 'isg_register_meta');

function isg_project_color_field($term = null): void {
    $color = $term instanceof WP_Term ? get_term_meta($term->term_id, 'isg_color', true) : '#0166ff';
    $field = '<label for="isg-project-color">' . esc_html__('Project color', 'isg') . '</label><input id="isg-project-color" name="isg_project_color" type="color" value="' . esc_attr($color ?: '#0166ff') . '">';
    if ($term instanceof WP_Term) {
        echo '<tr class="form-field"><th scope="row">' . esc_html__('Project color', 'isg') . '</th><td>' . $field;
        wp_nonce_field('isg_project_color', 'isg_project_color_nonce');
        echo '</td></tr>';
    } else {
        echo '<div class="form-field">' . $field;
        wp_nonce_field('isg_project_color', 'isg_project_color_nonce');
        echo '</div>';
    }
}
add_action('isg_download_project_add_form_fields', 'isg_project_color_field');
add_action('isg_download_project_edit_form_fields', 'isg_project_color_field');

function isg_save_project_color(int $term_id): void {
    $nonce = isset($_POST['isg_project_color_nonce']) ? sanitize_text_field(wp_unslash($_POST['isg_project_color_nonce'])) : '';
    if (!wp_verify_nonce($nonce, 'isg_project_color') || !current_user_can('manage_categories')) { return; }
    $color = isset($_POST['isg_project_color']) ? sanitize_hex_color(wp_unslash($_POST['isg_project_color'])) : null;
    if ($color) { update_term_meta($term_id, 'isg_color', $color); }
}
add_action('created_isg_download_project', 'isg_save_project_color');
add_action('edited_isg_download_project', 'isg_save_project_color');

function isg_include_content_in_search(WP_Query $query): void {
    if (!$query->is_main_query() || is_admin() || !$query->is_search()) {
        return;
    }
    $query->set('post_type', array('post', 'page', 'isg_product', 'isg_service', 'isg_download', 'isg_case', 'isg_job', 'isg_video'));
}
add_action('pre_get_posts', 'isg_include_content_in_search');

add_filter('get_the_archive_title', static function (string $title): string {
    if (is_home() && get_option('page_for_posts')) {
        return get_the_title((int) get_option('page_for_posts'));
    }
    if (is_post_type_archive()) {
        $type = get_queried_object();
        return $type instanceof WP_Post_Type ? $type->labels->name : $title;
    }
    if (is_tax()) {
        return single_term_title('', false);
    }
    return $title;
});

function isg_meta_box(): void {
    foreach (array('isg_download', 'isg_slide', 'isg_product', 'isg_service', 'isg_video') as $type) {
        add_meta_box('isg-link', __('External link', 'isg'), 'isg_link_fields', $type, 'side');
    }
    foreach (array('isg_product', 'isg_download', 'isg_case') as $type) {
        add_meta_box('isg-product-relationship', __('Product relationship', 'isg'), 'isg_relationship_fields', $type, 'side');
    }
}
add_action('add_meta_boxes', 'isg_meta_box');

function isg_relationship_fields(WP_Post $post): void {
    wp_nonce_field('isg_save_meta', 'isg_relationship_nonce');
    if ($post->post_type === 'isg_product') {
        $selected = (int) get_post_meta($post->ID, '_isg_shop_product_id', true);
        $products = get_posts(array('post_type' => 'product', 'post_status' => 'publish', 'numberposts' => -1, 'orderby' => 'title', 'order' => 'ASC'));
        echo '<p><label for="isg-shop-product">' . esc_html__('WooCommerce item', 'isg') . '</label></p>';
        echo '<select id="isg-shop-product" name="isg_shop_product_id" style="width:100%"><option value="0">' . esc_html__('None', 'isg') . '</option>';
        foreach ($products as $product) {
            echo '<option value="' . esc_attr($product->ID) . '" ' . selected($selected, $product->ID, false) . '>' . esc_html($product->post_title) . '</option>';
        }
        echo '</select>';
        return;
    }
    $selected = (int) get_post_meta($post->ID, '_isg_related_product', true);
    $products = get_posts(array('post_type' => 'isg_product', 'post_status' => 'publish', 'numberposts' => -1, 'orderby' => 'title', 'order' => 'ASC'));
    echo '<p><label for="isg-related-product">' . esc_html__('Related ISG product', 'isg') . '</label></p>';
    echo '<select id="isg-related-product" name="isg_related_product" style="width:100%"><option value="0">' . esc_html__('None', 'isg') . '</option>';
    foreach ($products as $product) {
        echo '<option value="' . esc_attr($product->ID) . '" ' . selected($selected, $product->ID, false) . '>' . esc_html($product->post_title) . '</option>';
    }
    echo '</select>';
}

function isg_link_fields(WP_Post $post): void {
    wp_nonce_field('isg_save_meta', 'isg_meta_nonce');
    $url = get_post_meta($post->ID, '_isg_external_url', true);
    echo '<p><label for="isg-external-url">' . esc_html__('URL', 'isg') . '</label></p>';
    echo '<input id="isg-external-url" name="isg_external_url" type="url" style="width:100%" value="' . esc_attr($url) . '">';
    if ($post->post_type === 'isg_download') {
        foreach (array('_isg_file_type' => __('File type', 'isg'), '_isg_file_size' => __('File size', 'isg')) as $key => $label) {
            echo '<p><label for="' . esc_attr($key) . '">' . esc_html($label) . '</label></p>';
            echo '<input id="' . esc_attr($key) . '" name="' . esc_attr($key) . '" type="text" style="width:100%" value="' . esc_attr(get_post_meta($post->ID, $key, true)) . '">';
        }
    }
    if ($post->post_type === 'isg_slide') {
        echo '<p><label for="isg-video-url">' . esc_html__('Video URL (MP4 or WebM)', 'isg') . '</label></p>';
        echo '<input id="isg-video-url" name="isg_video_url" type="url" style="width:100%" value="' . esc_attr(get_post_meta($post->ID, '_isg_video_url', true)) . '">';
    }
    if ($post->post_type === 'isg_video') {
        echo '<p><label for="isg-duration">' . esc_html__('Duration', 'isg') . '</label></p>';
        echo '<input id="isg-duration" name="isg_duration" type="text" style="width:100%" value="' . esc_attr(get_post_meta($post->ID, '_isg_duration', true)) . '">';
    }
}

function isg_save_meta(int $post_id): void {
    $nonce = $_POST['isg_meta_nonce'] ?? $_POST['isg_relationship_nonce'] ?? '';
    if (!wp_verify_nonce(sanitize_text_field(wp_unslash($nonce)), 'isg_save_meta')) {
        return;
    }
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE || !current_user_can('edit_post', $post_id)) {
        return;
    }
    if (isset($_POST['isg_external_url'])) {
        update_post_meta($post_id, '_isg_external_url', esc_url_raw(wp_unslash($_POST['isg_external_url'])));
    }
    foreach (array('_isg_file_type', '_isg_file_size') as $key) {
        if (isset($_POST[$key])) {
            update_post_meta($post_id, $key, sanitize_text_field(wp_unslash($_POST[$key])));
        }
    }
    if (isset($_POST['isg_video_url'])) {
        update_post_meta($post_id, '_isg_video_url', esc_url_raw(wp_unslash($_POST['isg_video_url'])));
    }
    if (isset($_POST['isg_duration'])) {
        update_post_meta($post_id, '_isg_duration', sanitize_text_field(wp_unslash($_POST['isg_duration'])));
    }
    if (isset($_POST['isg_related_product']) && in_array(get_post_type($post_id), array('isg_case', 'isg_download'), true)) {
        $related = absint($_POST['isg_related_product']);
        update_post_meta($post_id, '_isg_related_product', $related && get_post_type($related) === 'isg_product' ? $related : 0);
    }
    if (isset($_POST['isg_shop_product_id']) && get_post_type($post_id) === 'isg_product') {
        $shop_id = absint($_POST['isg_shop_product_id']);
        update_post_meta($post_id, '_isg_shop_product_id', $shop_id && get_post_type($shop_id) === 'product' ? $shop_id : 0);
    }
}
add_action('save_post', 'isg_save_meta');

function isg_customize(WP_Customize_Manager $manager): void {
    $manager->add_section('isg_company', array('title' => __('ISG company details', 'isg'), 'priority' => 35));
    foreach (array(
        'isg_tagline' => array('Homepage introduction', 'Software, self-service devices and connected systems. Innovation for life.', 'text'),
        'isg_email' => array('General email', 'info@isg.dev', 'email'),
        'isg_sales_email' => array('Sales email', 'sales@isg.dev', 'email'),
        'isg_telegram' => array('Telegram URL', 'https://t.me/infsysgroup', 'url'),
        'isg_x' => array('X URL', '', 'url'),
        'isg_linkedin' => array('LinkedIn URL', '', 'url'),
        'isg_instagram' => array('Instagram URL', '', 'url'),
        'isg_youtube' => array('YouTube URL', '', 'url'),
        'isg_facebook' => array('Facebook URL', '', 'url'),
        'isg_stat_1_value' => array('Statistic 1 value', '2006', 'text'),
        'isg_stat_1_label' => array('Statistic 1 label', 'Year the group began', 'text'),
        'isg_stat_2_value' => array('Statistic 2 value', '20+', 'text'),
        'isg_stat_2_label' => array('Statistic 2 label', 'Types of devices supported by ALLVEND', 'text'),
        'isg_stat_3_value' => array('Statistic 3 value', '5 min', 'text'),
        'isg_stat_3_label' => array('Statistic 3 label', 'Typical ALLVEND kiosk setup', 'text'),
        'isg_why_1_title' => array('Reason 1 title', 'Software and devices', 'text'),
        'isg_why_1_text' => array('Reason 1 text', 'Kiosk software and hardware are developed as connected solutions.', 'text'),
        'isg_why_2_title' => array('Reason 2 title', 'Transaction systems', 'text'),
        'isg_why_2_text' => array('Reason 2 text', 'SkySend connects payment processing, partners and service providers.', 'text'),
        'isg_why_3_title' => array('Reason 3 title', 'Deployment support', 'text'),
        'isg_why_3_text' => array('Reason 3 text', 'The team covers system design, implementation and technical services.', 'text'),
    ) as $key => $setting) {
        $manager->add_setting($key, array('default' => $setting[1], 'sanitize_callback' => $setting[2] === 'email' ? 'sanitize_email' : ($setting[2] === 'url' ? 'esc_url_raw' : 'sanitize_text_field')));
        $manager->add_control($key, array('section' => 'isg_company', 'label' => __($setting[0], 'isg'), 'type' => $setting[2]));
    }
    $manager->add_setting('isg_download_columns', array('default' => 3, 'sanitize_callback' => static function ($value): int { return in_array((int) $value, array(2, 3), true) ? (int) $value : 3; }));
    $manager->add_control('isg_download_columns', array('section' => 'isg_company', 'label' => __('Download grid columns', 'isg'), 'type' => 'select', 'choices' => array(2 => '2', 3 => '3')));
}
add_action('customize_register', 'isg_customize');

function isg_breadcrumbs(): void {
    if (is_front_page()) {
        return;
    }
    echo '<nav class="crumbs" aria-label="' . esc_attr__('Breadcrumbs', 'isg') . '"><a href="' . esc_url(home_url('/')) . '">' . esc_html__('Home', 'isg') . '</a><span>›</span>';
    if (is_page()) {
        foreach (array_reverse(get_post_ancestors(get_the_ID())) as $ancestor) {
            echo '<a href="' . esc_url(get_permalink($ancestor)) . '">' . esc_html(get_the_title($ancestor)) . '</a><span>›</span>';
        }
    }
    if (is_singular(array('isg_product', 'isg_service', 'isg_download', 'isg_case', 'isg_partner', 'isg_job'))) {
        $type = get_post_type_object(get_post_type());
        echo '<a href="' . esc_url(get_post_type_archive_link(get_post_type())) . '">' . esc_html($type->labels->name) . '</a><span>›</span>';
    }
    $label = is_singular() ? get_the_title() : (is_search() ? __('Search', 'isg') : get_the_archive_title());
    echo '<span>' . esc_html(wp_strip_all_tags($label)) . '</span><span class="crumb-social">';
    isg_social_links();
    echo '</span></nav>';
}

function isg_social_links(): void {
    $profiles = array('isg_telegram' => 'Telegram', 'isg_x' => 'X', 'isg_linkedin' => 'LinkedIn', 'isg_instagram' => 'Instagram', 'isg_youtube' => 'YouTube', 'isg_facebook' => 'Facebook');
    foreach ($profiles as $setting => $label) {
        $url = get_theme_mod($setting, $setting === 'isg_telegram' ? 'https://t.me/infsysgroup' : '');
        if ($url) {
            echo '<a href="' . esc_url($url) . '" target="_blank" rel="noopener" aria-label="' . esc_attr($label) . '">' . esc_html($label) . '</a>';
        }
    }
}

function isg_archive_link(string $post_type): string {
    $link = get_post_type_archive_link($post_type);
    return $link ? $link : home_url('/');
}
