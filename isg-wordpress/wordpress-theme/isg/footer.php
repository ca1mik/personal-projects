<?php if (!defined('ABSPATH')) { exit; } ?>
<footer class="footer">
  <div class="wrap">
    <div class="footer-main">
      <div>
        <a class="brand" href="<?php echo esc_url(home_url('/')); ?>"><img src="<?php echo esc_url(get_template_directory_uri() . '/assets/logo.png'); ?>" alt=""><span>ISG.DEV<small>INNOVATION FOR LIFE</small></span></a>
        <p><?php echo esc_html(get_theme_mod('isg_tagline', 'Software, self-service devices and connected systems. Innovation for life.')); ?></p>
      </div>
      <div><h3><?php esc_html_e('Explore', 'isg'); ?></h3>
        <a href="<?php echo esc_url(isg_archive_link('isg_product')); ?>"><?php esc_html_e('Products', 'isg'); ?></a>
        <a href="<?php echo esc_url(isg_archive_link('isg_service')); ?>"><?php esc_html_e('Services', 'isg'); ?></a>
        <a href="<?php echo esc_url(isg_archive_link('isg_download')); ?>"><?php esc_html_e('Downloads', 'isg'); ?></a>
        <a href="<?php echo esc_url(function_exists('wc_get_page_permalink') ? wc_get_page_permalink('shop') : 'mailto:' . get_theme_mod('isg_sales_email', 'sales@isg.dev') . '?subject=Product%20inquiry'); ?>"><?php esc_html_e('Buy', 'isg'); ?></a>
      </div>
      <div><h3><?php esc_html_e('Company', 'isg'); ?></h3>
        <?php if (has_nav_menu('footer')) : wp_nav_menu(array('theme_location' => 'footer', 'container' => false, 'menu_class' => 'footer-menu', 'depth' => 1)); else : ?>
          <a href="<?php echo esc_url(home_url('/company/')); ?>"><?php esc_html_e('About ISG', 'isg'); ?></a>
          <a href="<?php echo esc_url(isg_archive_link('isg_job')); ?>"><?php esc_html_e('Careers', 'isg'); ?></a>
        <?php endif; ?>
      </div>
      <div><h3><?php esc_html_e('Contact', 'isg'); ?></h3>
        <?php $email = get_theme_mod('isg_email', 'info@isg.dev'); ?>
        <a href="mailto:<?php echo esc_attr(antispambot($email)); ?>"><?php echo esc_html(antispambot($email)); ?></a>
        <?php isg_social_links(); ?>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© 2006–<?php echo esc_html(wp_date('Y')); ?> Inform Systems Group</span>
      <span><?php if (get_privacy_policy_url()) : ?><a href="<?php echo esc_url(get_privacy_policy_url()); ?>"><?php esc_html_e('Privacy policy', 'isg'); ?></a> · <?php endif; ?><a href="<?php echo esc_url(home_url('/wp-sitemap.xml')); ?>"><?php esc_html_e('Site map', 'isg'); ?></a></span>
    </div>
  </div>
</footer>
<?php wp_footer(); ?>
</body></html>
