<?php if (!defined('ABSPATH')) { exit; } ?>
<!doctype html>
<html <?php language_attributes(); ?>>
<head>
  <meta charset="<?php bloginfo('charset'); ?>">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>
<a class="skip-link screen-reader-text" href="#main"><?php esc_html_e('Skip to content', 'isg'); ?></a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="<?php echo esc_url(home_url('/')); ?>" aria-label="<?php esc_attr_e('Inform Systems Group home', 'isg'); ?>">
      <?php if (has_custom_logo()) : $logo_id = get_theme_mod('custom_logo'); echo wp_get_attachment_image($logo_id, 'thumbnail', false, array('alt' => '')); else : ?>
        <img src="<?php echo esc_url(get_template_directory_uri() . '/assets/logo.png'); ?>" alt="">
      <?php endif; ?>
      <span>ISG.DEV<small>INNOVATION FOR LIFE</small></span>
    </a>
    <nav class="main-nav" aria-label="<?php esc_attr_e('Main navigation', 'isg'); ?>">
      <?php if (has_nav_menu('primary')) :
          wp_nav_menu(array('theme_location' => 'primary', 'container' => false, 'menu_class' => 'isg-menu', 'depth' => 2));
      else : ?>
        <a href="<?php echo esc_url(isg_archive_link('isg_product')); ?>"><?php esc_html_e('Products', 'isg'); ?></a>
        <a href="<?php echo esc_url(isg_archive_link('isg_service')); ?>"><?php esc_html_e('Services', 'isg'); ?></a>
        <a href="<?php echo esc_url(home_url('/industries/')); ?>"><?php esc_html_e('Industries', 'isg'); ?></a>
        <a href="<?php echo esc_url(home_url('/company/')); ?>"><?php esc_html_e('Company', 'isg'); ?></a>
        <a href="<?php echo esc_url(home_url('/support/')); ?>"><?php esc_html_e('Support', 'isg'); ?></a>
      <?php endif; ?>
    </nav>
    <div class="header-actions">
      <?php $shop = function_exists('wc_get_page_permalink') ? wc_get_page_permalink('shop') : 'mailto:' . get_theme_mod('isg_sales_email', 'sales@isg.dev') . '?subject=Product%20inquiry'; ?>
      <a class="btn blue buy" href="<?php echo esc_url($shop); ?>"><?php esc_html_e('Buy', 'isg'); ?></a>
      <?php $telegram = get_theme_mod('isg_telegram', 'https://t.me/infsysgroup'); ?>
      <a class="icon-btn telegram" title="Telegram" aria-label="Telegram" href="<?php echo esc_url($telegram); ?>" target="_blank" rel="noopener">↗</a>
      <?php if (function_exists('pll_the_languages')) : ?>
        <div class="isg-language"><?php pll_the_languages(array('dropdown' => 1, 'show_names' => 0)); ?></div>
      <?php endif; ?>
      <button class="icon-btn" type="button" data-search-open aria-label="<?php esc_attr_e('Search', 'isg'); ?>" title="<?php esc_attr_e('Search', 'isg'); ?>">⌕</button>
      <button class="icon-btn menu-button" type="button" data-menu-toggle aria-expanded="false" aria-controls="mobile-navigation" aria-label="<?php esc_attr_e('Menu', 'isg'); ?>">☰</button>
    </div>
  </div>
  <nav class="mobile-panel" id="mobile-navigation" aria-label="<?php esc_attr_e('Mobile navigation', 'isg'); ?>" hidden>
    <?php if (has_nav_menu('primary')) : wp_nav_menu(array('theme_location' => 'primary', 'container' => false, 'menu_class' => 'mobile-menu', 'depth' => 1)); else : ?>
      <a href="<?php echo esc_url(isg_archive_link('isg_product')); ?>"><?php esc_html_e('Products', 'isg'); ?></a>
      <a href="<?php echo esc_url(isg_archive_link('isg_service')); ?>"><?php esc_html_e('Services', 'isg'); ?></a>
      <a href="<?php echo esc_url(home_url('/industries/')); ?>"><?php esc_html_e('Industries', 'isg'); ?></a>
      <a href="<?php echo esc_url(home_url('/company/')); ?>"><?php esc_html_e('Company', 'isg'); ?></a>
      <a href="<?php echo esc_url(home_url('/support/')); ?>"><?php esc_html_e('Support', 'isg'); ?></a>
      <a href="<?php echo esc_url($shop); ?>"><?php esc_html_e('Buy', 'isg'); ?></a>
    <?php endif; ?>
  </nav>
</header>
<div class="search-overlay" data-search-overlay hidden>
  <div class="search-box" role="dialog" aria-modal="true" aria-label="<?php esc_attr_e('Site search', 'isg'); ?>">
    <div class="search-box-head"><strong><?php esc_html_e('Search ISG', 'isg'); ?></strong><button class="icon-btn" type="button" data-search-close aria-label="<?php esc_attr_e('Close', 'isg'); ?>">×</button></div>
    <?php get_search_form(); ?>
  </div>
</div>
