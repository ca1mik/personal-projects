<?php get_header(); ?>
<main id="main"><div class="wrap woocommerce-area">
  <?php if (is_shop() && (int) wp_count_posts('product')->publish === 0) : ?>
    <h1><?php esc_html_e('Shop', 'isg'); ?></h1>
    <p class="lead"><?php esc_html_e('Contact ISG for current pricing and availability.', 'isg'); ?></p>
    <?php $solutions = get_posts(array('post_type' => 'isg_product', 'post_name__in' => array('solflare-card', 'allvend', 'skysend', 'fastsys'), 'numberposts' => 4, 'orderby' => 'post_name__in'));
    if ($solutions) : ?><div class="product-grid"><?php foreach ($solutions as $solution) : get_template_part('template-parts/card', null, array('post' => $solution)); endforeach; ?></div><?php endif; ?>
  <?php else : woocommerce_content(); endif; ?>
</div></main>
<?php get_footer(); ?>
