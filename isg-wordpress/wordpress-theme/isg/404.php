<?php get_header(); ?>
<main id="main"><div class="page-intro"><div class="wrap"><h1><?php esc_html_e('Page not found', 'isg'); ?></h1><p><?php esc_html_e('The requested page is not available.', 'isg'); ?></p><a class="btn blue" href="<?php echo esc_url(home_url('/')); ?>"><?php esc_html_e('Back to home', 'isg'); ?></a></div></div></main>
<?php get_footer(); ?>
