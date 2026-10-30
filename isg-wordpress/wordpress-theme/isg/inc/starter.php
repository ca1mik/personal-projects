<?php
/** Optional starter content import for a new ISG installation. */

if (!defined('ABSPATH')) { exit; }

function isg_starter_menu(): void {
    add_management_page(__('ISG starter content', 'isg'), __('ISG starter content', 'isg'), 'manage_options', 'isg-starter', 'isg_starter_page');
}
add_action('admin_menu', 'isg_starter_menu');

function isg_starter_page(): void {
    if (!current_user_can('manage_options')) { return; }
    echo '<div class="wrap"><h1>' . esc_html__('ISG starter content', 'isg') . '</h1>';
    echo '<p>' . esc_html__('Creates initial company pages, product and service entries, downloads, and homepage slides. Existing entries with matching slugs are left as they are.', 'isg') . '</p>';
    if (isset($_GET['imported'])) {
        echo '<div class="notice notice-success"><p>' . esc_html__('Starter content is ready.', 'isg') . '</p></div>';
    }
    echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="isg_seed">';
    wp_nonce_field('isg_seed_content');
    submit_button(__('Create starter content', 'isg'));
    echo '</form></div>';
}

function isg_seed_image(string $filename): int {
    $saved = get_option('isg_seed_media_ids', array());
    if (isset($saved[$filename]) && get_post_status((int) $saved[$filename])) {
        return (int) $saved[$filename];
    }
    $file = get_template_directory() . '/assets/' . $filename;
    if (!is_readable($file)) { return 0; }
    $upload = wp_upload_bits($filename, null, file_get_contents($file));
    if (!empty($upload['error'])) { return 0; }
    $attachment = wp_insert_attachment(array(
        'post_title' => sanitize_text_field(pathinfo($filename, PATHINFO_FILENAME)),
        'post_mime_type' => 'image/webp',
        'post_status' => 'inherit',
    ), $upload['file']);
    if (is_wp_error($attachment)) { return 0; }
    require_once ABSPATH . 'wp-admin/includes/image.php';
    wp_update_attachment_metadata($attachment, wp_generate_attachment_metadata($attachment, $upload['file']));
    $saved[$filename] = $attachment;
    update_option('isg_seed_media_ids', $saved, false);
    return $attachment;
}

function isg_seed_post(string $type, string $slug, string $title, string $excerpt, string $content = '', string $image = '', array $meta = array()): int {
    $existing = get_page_by_path($slug, OBJECT, $type);
    if ($existing && $existing->post_type !== $type) {
        $existing = null;
    }
    if (!$existing) {
        $matches = get_posts(array('post_type' => $type, 'name' => $slug, 'post_status' => 'any', 'numberposts' => 1));
        $existing = $matches[0] ?? null;
    }
    if ($existing) { return (int) $existing->ID; }
    $id = wp_insert_post(array(
        'post_type' => $type, 'post_status' => 'publish', 'post_name' => $slug,
        'post_title' => $title, 'post_excerpt' => $excerpt, 'post_content' => wp_kses_post($content),
    ), true);
    if (is_wp_error($id)) { return 0; }
    if ($image) {
        $attachment = isg_seed_image($image);
        if ($attachment) { set_post_thumbnail($id, $attachment); }
    }
    foreach ($meta as $key => $value) {
        update_post_meta($id, $key, $value);
    }
    return (int) $id;
}

function isg_seed_terms(int $post_id, string $taxonomy, array $names): void {
    $ids = array();
    foreach ($names as $name) {
        $term = term_exists($name, $taxonomy);
        if (!$term) { $term = wp_insert_term($name, $taxonomy); }
        if (!is_wp_error($term)) {
            $ids[] = (int) (is_array($term) ? $term['term_id'] : $term);
        }
    }
    if ($ids) { wp_set_object_terms($post_id, $ids, $taxonomy, true); }
}

function isg_seed_navigation(): void {
    $menu = wp_get_nav_menu_object('ISG primary');
    $menu_id = $menu && !is_wp_error($menu) ? (int) $menu->term_id : wp_create_nav_menu('ISG primary');
    if (is_wp_error($menu_id) || !$menu_id) { return; }
    if (!wp_get_nav_menu_items($menu_id)) {
        $top = array(
            'Products' => isg_archive_link('isg_product'),
            'Services' => isg_archive_link('isg_service'),
            'Industries' => home_url('/industries/'),
            'Company' => home_url('/company/'),
            'Support' => home_url('/support/'),
        );
        $parents = array();
        foreach ($top as $label => $url) {
            $parents[$label] = wp_update_nav_menu_item($menu_id, 0, array('menu-item-title' => $label, 'menu-item-url' => $url, 'menu-item-status' => 'publish'));
        }
        $children = array(
            'Products' => array('Developments', 'Devices', 'Innovations', 'Technologies'),
            'Services' => array('Web3', 'SkySend', 'Software development', 'Analysis', 'Deployment'),
        );
        foreach ($children as $parent => $names) {
            $taxonomy = $parent === 'Products' ? 'isg_product_type' : 'isg_service_group';
            foreach ($names as $name) {
                $term = get_term_by('name', $name, $taxonomy);
                if ($term) {
                    wp_update_nav_menu_item($menu_id, 0, array('menu-item-title' => $name, 'menu-item-url' => get_term_link($term), 'menu-item-parent-id' => $parents[$parent], 'menu-item-status' => 'publish'));
                }
            }
        }
        $industries = get_terms(array('taxonomy' => 'isg_industry', 'hide_empty' => false));
        if (!is_wp_error($industries)) {
            foreach ($industries as $industry) {
                wp_update_nav_menu_item($menu_id, 0, array('menu-item-title' => $industry->name, 'menu-item-url' => get_term_link($industry), 'menu-item-parent-id' => $parents['Industries'], 'menu-item-status' => 'publish'));
            }
        }
        foreach (array('mission', 'history', 'licenses', 'partnership', 'careers', 'contacts') as $slug) {
            $page = get_page_by_path('company/' . $slug);
            if ($page) {
                wp_update_nav_menu_item($menu_id, 0, array('menu-item-title' => $page->post_title, 'menu-item-object-id' => $page->ID, 'menu-item-object' => 'page', 'menu-item-type' => 'post_type', 'menu-item-parent-id' => $parents['Company'], 'menu-item-status' => 'publish'));
            }
        }
        foreach (array('Downloads' => isg_archive_link('isg_download'), 'Feedback' => home_url('/support/feedback/')) as $label => $url) {
            wp_update_nav_menu_item($menu_id, 0, array('menu-item-title' => $label, 'menu-item-url' => $url, 'menu-item-parent-id' => $parents['Support'], 'menu-item-status' => 'publish'));
        }
    }
    $locations = get_theme_mod('nav_menu_locations', array());
    if (empty($locations['primary'])) {
        $locations['primary'] = $menu_id;
        set_theme_mod('nav_menu_locations', $locations);
    }
}

function isg_seed_shop_drafts(): void {
    if (!class_exists('WC_Product_Simple')) { return; }
    $items = array(
        array('solflare-card', 'Solflare Mastercard', 'Web3', 'The Solflare card offering described in the official ISG presentation.'),
        array('passive-income', 'Passive income setup', 'Services', 'Service scope and price require approval before publication.'),
        array('allvend', 'ALLVEND software', 'Software', 'ALLVEND software licensing and delivery terms require approval before publication.'),
        array('skysend', 'SkySend processing', 'Financial systems', 'SkySend connection and pricing terms require approval before publication.'),
    );
    foreach ($items as [$sku_suffix, $name, $category, $description]) {
        if (wc_get_product_id_by_sku('isg-brief-' . $sku_suffix)) { continue; }
        $term = term_exists($category, 'product_cat');
        if (!$term) { $term = wp_insert_term($category, 'product_cat'); }
        $product = new WC_Product_Simple();
        $product->set_name($name);
        $product->set_status('draft');
        $product->set_catalog_visibility('visible');
        $product->set_sku('isg-brief-' . $sku_suffix);
        $product->set_description($description);
        if (!is_wp_error($term)) {
            $product->set_category_ids(array((int) (is_array($term) ? $term['term_id'] : $term)));
        }
        $product->save();
    }
}

function isg_seed_news(): void {
    $items = array(
        array('dear-polkadot-validators', 'Dear Polkadot Validators', '2024-12-20 15:16:53', 'ISG published an update for Polkadot validators about an infrastructure migration.', '', 'https://isg.dev/news/dear-polkadot-validators/'),
        array('dear-nominators-of-polkadot-network', 'Dear nominators of Polkadot network', '2022-12-19 11:05:11', 'ISG shared an infrastructure update with Polkadot nominators.', 'news-nominators.webp', 'https://isg.dev/news/dear-nominators-of-polkadot-network/'),
        array('business-mission-az', 'Business mission in Azerbaijan', '2022-09-28 17:15:41', 'Inform Systems Group took part in a business mission to Azerbaijan.', 'news-azerbaijan.webp', 'https://isg.dev/news/business-mission-az/'),
    );
    foreach ($items as [$slug, $title, $date, $excerpt, $image, $source]) {
        if (get_page_by_path($slug, OBJECT, 'post')) { continue; }
        $content = '<p>' . esc_html($excerpt) . '</p><p><a href="' . esc_url($source) . '" target="_blank" rel="noopener">Read the original ISG publication</a></p>';
        $id = isg_seed_post('post', $slug, $title, $excerpt, $content, $image);
        if ($id) { wp_update_post(array('ID' => $id, 'post_date' => $date)); }
    }
}

function isg_seed_content(): void {
    if (!current_user_can('manage_options')) { wp_die(esc_html__('Insufficient permissions.', 'isg')); }
    check_admin_referer('isg_seed_content');
    isg_seed_data();
    wp_safe_redirect(add_query_arg('imported', '1', admin_url('tools.php?page=isg-starter')));
    exit;
}

function isg_seed_data(): void {
    $home = isg_seed_post('page', 'home', 'Home', 'Inform Systems Group homepage.');
    $news = isg_seed_post('page', 'news', 'News', 'Updates from Inform Systems Group.');
    $company = isg_seed_post('page', 'company', 'Company', 'Innovation for life.', '<h2>Innovation for life</h2><p>Inform Systems Group develops software, hardware and connected systems for self-service, financial and public services.</p><p>Our work brings together operating systems, payment processing, devices and digital services.</p>');
    isg_seed_post('page', 'industries', 'Industries', 'ISG solutions for different sectors.');
    $support = isg_seed_post('page', 'support', 'Support', '', '<p>Find technical materials or contact the ISG team.</p>');
    $company_pages = array(
        array('mission', 'Mission', '<p>Innovation for life is the guiding idea behind ISG software, devices and services.</p>'),
        array('history', 'History', '<p>Inform Systems Group began in 2006. This page is ready for an approved company timeline.</p>'),
        array('licenses', 'Licenses and certificates', '<p>Official documents and certificates are listed below.</p>'),
        array('partnership', 'Partnership', '<p>Explore cooperation in Web3, software and services, international technology development and SkySend.</p>'),
        array('careers', 'Careers', '<p>Current openings and application contacts are listed below.</p>'),
        array('contacts', 'Contacts', '<p>Contact Inform Systems Group about products, services and support.</p>'),
    );
    foreach ($company_pages as [$slug, $title, $content]) {
        $id = isg_seed_post('page', $slug, $title, '', $content);
        if ($id && $company && (int) get_post_field('post_parent', $id) !== $company) {
            wp_update_post(array('ID' => $id, 'post_parent' => $company));
        }
    }
    $feedback = isg_seed_post('page', 'feedback', 'Support and feedback', '', '<p>For support, contact the ISG team by email or Telegram.</p>');
    if ($feedback && $support && (int) get_post_field('post_parent', $feedback) !== $support) {
        wp_update_post(array('ID' => $feedback, 'post_parent' => $support));
    }
    if ($home && !get_option('page_on_front')) {
        update_option('show_on_front', 'page');
        update_option('page_on_front', $home);
    }
    if ($news && !get_option('page_for_posts')) {
        update_option('page_for_posts', $news);
    }

    foreach (array('Individuals', 'Kiosk manufacturers', 'Banks and finance', 'Healthcare', 'Automotive', 'System integrators', 'Quick service restaurants', 'Public sector', 'Telecom operators', 'Retail chains', 'Hospitality', 'Passenger transport', 'Construction') as $industry) {
        if (!term_exists($industry, 'isg_industry')) {
            wp_insert_term($industry, 'isg_industry');
        }
    }

    $products = array(
        array('allvend', 'ALLVEND', 'Software for self-service kiosks, information terminals and digital displays.', 'ALLVEND supports self-service devices and remote management.', 'allvend.webp', 'https://isg.dev/products/allvend/', 'Developments', array('Retail chains', 'Public sector', 'Passenger transport')),
        array('fastsys', 'FastSYS', 'An operating system for dedicated devices and infrastructure.', 'FastSYS is a UNIX-based operating system designed for embedded systems.', 'fastsys.webp', 'https://isg.dev/products/fastsys/', 'Developments', array('Automotive', 'System integrators')),
        array('skysend', 'SkySend', 'A processing system connecting service providers, payment points and digital channels.', 'SkySend brings payment processing, provider connections and partner interfaces together.', 'skysend.webp', 'https://isg.dev/products/skysend/', 'Developments', array('Banks and finance', 'Telecom operators')),
        array('beauty', 'Beauty', 'Configurable self-service kiosks for payments, information and customer services.', 'Beauty kiosks work with ALLVEND and can be configured for service tasks.', 'beauty.webp', 'https://isg.dev/products/beauty/', 'Devices', array('Retail chains', 'Hospitality')),
        array('finger', 'FINGER', 'Biometric technology for identification and digital services.', 'FINGER combines biometric hardware and software components.', '', '', 'Developments', array('Banks and finance')),
        array('cloud-advertising', 'Cloud advertising platform', 'Content management for networks of digital displays.', 'Manage advertising and information across connected displays.', 'innovation.webp', '', 'Developments', array('Retail chains')),
        array('smart-city', 'Smart City', 'Connected urban information and public services.', 'A unified information system for connected city services.', 'innovation.webp', '', 'Innovations', array('Public sector')),
        array('my-doctor', 'My Doctor', 'Digital healthcare and telemedicine services.', 'A telemedicine concept for more accessible care.', 'doctor.webp', 'https://isg.dev/products/meamed/', 'Innovations', array('Healthcare')),
        array('allvend-units', 'ALLVEND universal units', 'Hardware units for self-service devices.', 'Hardware components in the ALLVEND product family.', 'allvend.webp', '', 'Devices', array('Kiosk manufacturers', 'System integrators')),
        array('finger-units', 'FINGER biometric units', 'Biometric hardware units for identification.', 'Hardware components in the FINGER product family.', '', '', 'Devices', array('Banks and finance', 'Kiosk manufacturers')),
        array('fiscal-server', 'Unified fiscal server', 'A server component for fiscal operations.', 'A product area for fiscal server technology.', '', '', 'Devices', array('Retail chains')),
        array('neuron', 'Neuron technopark network', 'A network of technology parks.', 'An ISG innovation area focused on technology parks.', 'innovation.webp', '', 'Innovations', array('Construction', 'Public sector')),
        array('remote-binary-updates', 'Remote binary updates', 'Technology for remotely updating deployed systems.', 'A technology area for managed software updates.', 'fastsys.webp', '', 'Technologies', array('System integrators')),
        array('bsd-server-cloning', 'BSD server cloning', 'Technology for cloning BSD-based servers.', 'A technology area for server deployment.', 'fastsys.webp', '', 'Technologies', array('System integrators')),
        array('closed-key-exchange', 'Closed key exchange', 'Technology for protected cryptographic key exchange.', 'A technology area for secure key exchange.', '', '', 'Technologies', array('Banks and finance')),
        array('solflare-card', 'Solflare Mastercard', 'A card offering described in the official ISG presentation.', 'Explore the Solflare card offering and contact the team about availability and terms.', 'solflare.webp', 'https://ftp.isg.dev/offer/web3/solflare_card_offer.pdf', 'Innovations', array('Individuals', 'Banks and finance')),
    );
    foreach ($products as $entry) {
        [$slug, $title, $excerpt, $description, $image, $url, $kind, $sectors] = $entry;
        $id = isg_seed_post('isg_product', $slug, $title, $excerpt, '<h2>Overview</h2><p>' . esc_html($description) . '</p><h2>Materials and next steps</h2><p>For technical information and availability, contact our team or view the product materials.</p>', $image, array('_isg_external_url' => $url));
        if ($id) {
            isg_seed_terms($id, 'isg_product_type', array($kind));
            isg_seed_terms($id, 'isg_industry', $sectors);
        }
    }

    $services = array(
        array('web3', 'Web3 services', 'Device security, Solflare card registration and digital asset services.', 'Web3'),
        array('skysend-services', 'SkySend services', 'Payment processing, provider connections and custom service interfaces.', 'SkySend'),
        array('software-development', 'Software development', 'Embedded software, transaction systems, device drivers and APIs.', 'Software development'),
        array('it-design', 'IT design and audit', 'System architecture, technical specifications and operational documentation.', 'Analysis'),
        array('deployment', 'Solution deployment', 'Secure servers, IP telephony, video monitoring and public service automation.', 'Deployment'),
        array('solflare-card-registration', 'Solflare card registration', 'Registration support for Solflare cards.', 'Web3'),
        array('device-security', 'Device security setup', 'Security configuration for supported devices.', 'Web3'),
        array('passive-income-setup', 'Passive income setup', 'Configuration support for passive income services.', 'Web3'),
        array('payment-processing', 'Payment transaction processing', 'Transaction processing through SkySend.', 'SkySend'),
        array('custom-interfaces', 'Custom interfaces', 'Individual service interfaces for SkySend.', 'SkySend'),
        array('provider-connections', 'Provider connections', 'Connecting service providers to SkySend.', 'SkySend'),
        array('financial-services', 'Financial services', 'Financial service capabilities of SkySend.', 'SkySend'),
        array('cluster-systems', 'Cluster and transaction systems', 'Software for clustered and transactional workloads.', 'Software development'),
        array('embedded-software', 'Embedded software', 'Software for dedicated and embedded devices.', 'Software development'),
        array('peripheral-drivers', 'Peripheral device drivers', 'Drivers for peripheral hardware.', 'Software development'),
        array('transaction-apis', 'Transaction APIs', 'APIs for transaction-processing services.', 'Software development'),
        array('technical-specifications', 'Technical specifications', 'Preparation of technical requirements and specifications.', 'Analysis'),
        array('operational-instructions', 'Operational instructions', 'Preparation of instructions and operating regulations.', 'Analysis'),
        array('protected-servers', 'Protected servers', 'Deployment of cryptographically protected servers.', 'Deployment'),
        array('secure-ip-telephony', 'Secure IP telephony', 'Deployment of protected IP telephony.', 'Deployment'),
        array('key-exchange-deployment', 'Closed key exchange deployment', 'Deployment of protected key exchange systems.', 'Deployment'),
        array('intelligent-video', 'Intelligent video monitoring', 'Deployment of intelligent video monitoring.', 'Deployment'),
        array('mfc-automation', 'Public service center automation', 'Automation solutions for multifunctional public service centers.', 'Deployment'),
        array('certificate-authority', 'Certificate authority setup', 'Deployment of a certificate authority.', 'Deployment'),
    );
    foreach ($services as [$slug, $title, $excerpt, $group]) {
        $id = isg_seed_post('isg_service', $slug, $title, $excerpt, '<h2>Service overview</h2><p>' . esc_html($excerpt) . '</p><h2>Discuss your project</h2><p>Contact the ISG team to define scope, schedule and implementation details.</p>');
        if ($id) { isg_seed_terms($id, 'isg_service_group', array($group)); }
    }

    $files = array(
        array('solflare-card-offer', 'Solflare card offer', 'Web3', 'PDF', '4.5 MB', 'https://ftp.isg.dev/offer/web3/solflare_card_offer.pdf'),
        array('allvend-image', 'ALLVEND + FastSYS installation image', 'ALLVEND', 'ZIP', '488 MB', 'https://ftp.isg.dev/soft/allvend/fastsys5_allvend.iso.zip'),
        array('allvend-demo', 'ALLVEND demo', 'ALLVEND', 'ZIP', '480 MB', 'https://ftp.isg.dev/soft/demo/fs_5.248_av_10.demo.zip'),
        array('allvend-installation-guide', 'ALLVEND installation guide', 'ALLVEND', 'PDF', '685 KB', 'https://ftp.isg.dev/docs/instruction_installation_allvend.pdf'),
        array('allvend-registration', 'ALLVEND software registration', 'Company', 'PDF', '217 KB', 'https://ftp.isg.dev/license/certificate_registration_software_allvend.pdf'),
        array('fastsys-registration', 'FastSYS registration', 'Company', 'PDF', '226 KB', 'https://ftp.isg.dev/license/certificate_registration_os_fastsys.pdf'),
        array('skysend-registration', 'SkySend registration', 'Company', 'PDF', '217 KB', 'https://ftp.isg.dev/license/certificate_registration_processing_skysend.pdf'),
    );
    foreach ($files as [$slug, $title, $project, $type, $size, $url]) {
        $id = isg_seed_post('isg_download', $slug, $title, $type . ' · ' . $size, '', '', array('_isg_external_url' => $url, '_isg_file_type' => $type, '_isg_file_size' => $size));
        if ($id) {
            isg_seed_terms($id, 'isg_download_project', array($project));
            $project_term = get_term_by('name', $project, 'isg_download_project');
            if ($project_term && !get_term_meta($project_term->term_id, 'isg_color', true)) {
                update_term_meta($project_term->term_id, 'isg_color', array('ALLVEND' => '#0166ff', 'Web3' => '#d2a900', 'Company' => '#39ac59')[$project] ?? '#0166ff');
            }
            $product = get_page_by_path(sanitize_title($project), OBJECT, 'isg_product');
            if ($product && !get_post_meta($id, '_isg_related_product', true)) {
                update_post_meta($id, '_isg_related_product', $product->ID);
            }
        }
    }

    $slides = array(
        array('isg', 'Inform Systems Group', 'Software, self-service devices and connected systems. Innovation for life.', 'beauty.webp', isg_archive_link('isg_product')),
        array('solflare', 'Solflare Mastercard', 'Explore the card offering in the official ISG presentation.', 'solflare.webp', get_permalink(get_page_by_path('solflare-card', OBJECT, 'isg_product'))),
        array('allvend', 'ALLVEND', 'One platform for many kinds of self-service.', 'allvend.webp', isg_archive_link('isg_product')),
        array('smart-city', 'Smart City', 'Connected services for cities and citizens.', 'innovation.webp', isg_archive_link('isg_product')),
    );
    foreach ($slides as [$slug, $title, $excerpt, $image, $url]) {
        isg_seed_post('isg_slide', $slug, $title, $excerpt, '', $image, array('_isg_external_url' => $url));
    }
    isg_seed_navigation();
    isg_seed_shop_drafts();
    isg_seed_news();
}
add_action('admin_post_isg_seed', 'isg_seed_content');
