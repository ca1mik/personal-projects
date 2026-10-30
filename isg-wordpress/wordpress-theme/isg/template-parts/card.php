<?php
if (!defined('ABSPATH')) { exit; }
$post_item = $args['post'] ?? get_post();
if (!$post_item instanceof WP_Post) { return; }
$type = get_post_type_object($post_item->post_type);
?>
<article class="product-card">
  <a class="product-visual" href="<?php echo esc_url(get_permalink($post_item)); ?>">
    <?php if (has_post_thumbnail($post_item)) : echo get_the_post_thumbnail($post_item, 'isg-card', array('loading' => 'lazy', 'alt' => get_the_title($post_item))); else : ?>
      <img src="<?php echo esc_url(get_template_directory_uri() . '/assets/logo.png'); ?>" alt="" loading="lazy">
    <?php endif; ?>
  </a>
  <div class="product-card-body">
    <span class="card-kicker"><?php echo esc_html($type ? $type->labels->singular_name : __('Article', 'isg')); ?></span>
    <h3><?php echo esc_html(get_the_title($post_item)); ?></h3>
    <p><?php echo esc_html(get_the_excerpt($post_item)); ?></p>
    <a class="text-link" href="<?php echo esc_url(get_permalink($post_item)); ?>"><?php esc_html_e('Learn more', 'isg'); ?> →</a>
  </div>
</article>
