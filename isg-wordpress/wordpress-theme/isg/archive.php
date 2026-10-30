<?php get_header(); ?>
<main id="main">
  <div class="page-intro"><div class="wrap"><?php isg_breadcrumbs(); ?><h1><?php the_archive_title(); ?></h1><?php if (get_the_archive_description()) : ?><div class="lead"><?php the_archive_description(); ?></div><?php endif; ?></div></div>
  <?php $group_taxonomy = is_post_type_archive('isg_product') ? 'isg_product_type' : (is_post_type_archive('isg_service') ? 'isg_service_group' : '');
  $groups = $group_taxonomy ? get_terms(array('taxonomy' => $group_taxonomy, 'hide_empty' => true)) : array();
  if ($group_taxonomy && !is_wp_error($groups) && $groups) :
      foreach ($groups as $group) :
          $items = get_posts(array('post_type' => get_query_var('post_type'), 'numberposts' => -1, 'orderby' => 'menu_order', 'order' => 'ASC', 'tax_query' => array(array('taxonomy' => $group_taxonomy, 'field' => 'term_id', 'terms' => $group->term_id))));
          if (!$items) { continue; } ?>
          <section class="section"><div class="wrap"><div class="section-head"><h2 class="section-title"><?php echo esc_html($group->name); ?></h2></div><div class="catalog-grid"><?php foreach ($items as $item) : get_template_part('template-parts/card', null, array('post' => $item)); endforeach; ?></div></div></section>
      <?php endforeach;
  else : ?>
    <section class="section"><div class="wrap">
      <?php if (have_posts()) : ?><div class="catalog-grid"><?php while (have_posts()) : the_post(); get_template_part('template-parts/card', null, array('post' => get_post())); endwhile; ?></div>
        <nav class="pagination" aria-label="<?php esc_attr_e('Page navigation', 'isg'); ?>"><?php the_posts_pagination(array('mid_size' => 1, 'prev_text' => '←', 'next_text' => '→')); ?></nav>
      <?php else : ?><p class="empty"><?php esc_html_e('No items have been published yet.', 'isg'); ?></p><?php endif; ?>
    </div></section>
  <?php endif; ?>
</main>
<?php get_footer(); ?>
