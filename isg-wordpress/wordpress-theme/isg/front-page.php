<?php get_header(); ?>
<main id="main">
  <?php
  $slides = new WP_Query(array('post_type' => 'isg_slide', 'posts_per_page' => 4, 'orderby' => 'menu_order', 'order' => 'ASC'));
  if ($slides->have_posts()) :
      $slide_data = array();
      while ($slides->have_posts()) : $slides->the_post();
          $slide_data[] = array('title' => get_the_title(), 'text' => get_the_excerpt(), 'image' => get_the_post_thumbnail_url(get_the_ID(), 'full'), 'video' => get_post_meta(get_the_ID(), '_isg_video_url', true), 'link' => get_post_meta(get_the_ID(), '_isg_external_url', true));
      endwhile;
      wp_reset_postdata();
  else :
      $slide_data = array(array(
          'title' => 'Inform Systems Group',
          'text' => get_theme_mod('isg_tagline', 'Software, self-service devices and connected systems. Innovation for life.'),
          'image' => get_template_directory_uri() . '/assets/beauty.webp',
          'video' => '',
          'link' => isg_archive_link('isg_product'),
      ));
  endif;
  ?>
  <section class="hero" data-slider>
    <?php foreach ($slide_data as $index => $slide) : ?>
      <div class="hero-slide<?php echo $index === 0 ? ' active' : ''; ?>" data-slide-panel="<?php echo esc_attr($index); ?>" <?php echo $index === 0 ? '' : 'hidden'; ?>>
        <div class="wrap"><div class="hero-copy"><span class="hero-index"><?php echo esc_html(sprintf('%02d / %02d', $index + 1, count($slide_data))); ?> · ISG</span><h1><?php echo esc_html($slide['title']); ?></h1><p><?php echo esc_html($slide['text']); ?></p><a class="btn blue" href="<?php echo esc_url($slide['link'] ?: isg_archive_link('isg_product')); ?>"><?php esc_html_e('Explore', 'isg'); ?></a></div><div class="hero-media"><?php if (!empty($slide['video'])) : ?><video autoplay muted loop playsinline preload="metadata" poster="<?php echo esc_url($slide['image'] ?: ''); ?>"><source src="<?php echo esc_url($slide['video']); ?>"></video><?php else : ?><img src="<?php echo esc_url($slide['image'] ?: get_template_directory_uri() . '/assets/beauty.webp'); ?>" alt="" <?php echo $index === 0 ? 'fetchpriority="high"' : 'loading="lazy"'; ?>><?php endif; ?></div></div>
      </div>
    <?php endforeach; ?>
    <?php if (count($slide_data) > 1) : ?><div class="wrap hero-controls"><?php foreach ($slide_data as $index => $slide) : ?><button class="hero-dot<?php echo $index === 0 ? ' active' : ''; ?>" type="button" data-slide-target="<?php echo esc_attr($index); ?>" aria-label="<?php echo esc_attr(sprintf(__('Slide %d', 'isg'), $index + 1)); ?>"></button><?php endforeach; ?></div><?php endif; ?>
  </section>
  <?php if (have_posts()) : while (have_posts()) : the_post(); if (trim(get_the_content())) : ?><div class="entry-content"><?php the_content(); ?></div><?php endif; endwhile; endif; ?>
  <div class="stats"><div class="wrap stats-grid"><?php for ($number = 1; $number <= 3; $number++) : ?><div class="stat"><strong><?php echo esc_html(get_theme_mod('isg_stat_' . $number . '_value', array(1 => '2006', 2 => '20+', 3 => '5 min')[$number])); ?></strong><span><?php echo esc_html(get_theme_mod('isg_stat_' . $number . '_label', array(1 => 'Year the group began', 2 => 'Types of devices supported by ALLVEND', 3 => 'Typical ALLVEND kiosk setup')[$number])); ?></span></div><?php endfor; ?></div></div>
  <?php $latest = new WP_Query(array('post_type' => 'post', 'posts_per_page' => 3)); if ($latest->have_posts()) : ?>
    <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Updates', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('What is happening at ISG', 'isg'); ?></h2></div><a class="text-link" href="<?php echo esc_url(get_permalink(get_option('page_for_posts')) ?: home_url('/news/')); ?>"><?php esc_html_e('All news', 'isg'); ?> →</a></div><div class="news-grid">
      <?php while ($latest->have_posts()) : $latest->the_post(); ?><article class="news-card"><a class="news-visual" href="<?php the_permalink(); ?>"><?php if (has_post_thumbnail()) : the_post_thumbnail('isg-card', array('loading' => 'lazy', 'alt' => get_the_title())); else : ?><img src="<?php echo esc_url(get_template_directory_uri() . '/assets/logo.png'); ?>" alt="" loading="lazy"><?php endif; ?></a><time class="news-date" datetime="<?php echo esc_attr(get_the_date('c')); ?>"><?php echo esc_html(get_the_date() . ' · ' . get_the_time()); ?></time><h3><?php the_title(); ?></h3><p><?php echo esc_html(get_the_excerpt()); ?></p><a class="text-link" href="<?php the_permalink(); ?>"><?php esc_html_e('Read more', 'isg'); ?> &#8594;</a></article><?php endwhile; wp_reset_postdata(); ?>
    </div></div></section>
  <?php endif; ?>
  <?php if (class_exists('WooCommerce')) : $popular = new WP_Query(array('post_type' => 'product', 'posts_per_page' => 4, 'meta_key' => 'total_sales', 'orderby' => 'meta_value_num', 'order' => 'DESC')); if ($popular->have_posts()) : ?>
    <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Store', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('Popular purchases', 'isg'); ?></h2></div><a class="text-link" href="<?php echo esc_url(wc_get_page_permalink('shop')); ?>"><?php esc_html_e('All products', 'isg'); ?> →</a></div><div class="product-grid">
      <?php while ($popular->have_posts()) : $popular->the_post(); get_template_part('template-parts/card', null, array('post' => get_post())); endwhile; wp_reset_postdata(); ?>
    </div></div></section>
  <?php endif; endif; ?>
  <?php $featured = new WP_Query(array('post_type' => 'isg_product', 'posts_per_page' => 4, 'orderby' => 'menu_order', 'order' => 'ASC')); if ($featured->have_posts()) : ?>
    <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Solutions', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('Explore our technology', 'isg'); ?></h2></div><a class="text-link" href="<?php echo esc_url(isg_archive_link('isg_product')); ?>"><?php esc_html_e('All products', 'isg'); ?> →</a></div><div class="product-grid">
      <?php while ($featured->have_posts()) : $featured->the_post(); get_template_part('template-parts/card', null, array('post' => get_post())); endwhile; wp_reset_postdata(); ?>
    </div></div></section>
  <?php endif; ?>
  <?php $highlights = new WP_Query(array('post_type' => 'isg_product', 'post_name__in' => array('solflare-card', 'allvend', 'skysend', 'fastsys'), 'posts_per_page' => 4, 'orderby' => 'post_name__in')); if ($highlights->have_posts()) : $highlight_number = 0; while ($highlights->have_posts()) : $highlights->the_post(); ?>
    <section class="feature<?php echo $highlight_number % 2 ? ' reverse' : ''; ?><?php echo get_post_field('post_name') === 'solflare-card' ? ' solflare-feature' : ''; ?>"><div class="feature-media"><?php if (has_post_thumbnail()) : the_post_thumbnail('large', array('loading' => 'eager', 'alt' => get_the_title())); endif; ?></div><div class="feature-copy"><span class="eyebrow"><?php esc_html_e('ISG product', 'isg'); ?></span><h2><?php the_title(); ?></h2><p><?php echo esc_html(get_the_excerpt()); ?></p><div class="actions"><a class="btn blue" href="<?php the_permalink(); ?>"><?php esc_html_e('Learn more', 'isg'); ?></a><a class="btn outline" href="mailto:<?php echo esc_attr(get_theme_mod('isg_sales_email', 'sales@isg.dev')); ?>?subject=<?php echo rawurlencode(get_the_title() . ' inquiry'); ?>"><?php esc_html_e('Contact sales', 'isg'); ?></a></div></div></section>
  <?php $highlight_number++; endwhile; wp_reset_postdata(); endif; ?>
  <?php $jobs = new WP_Query(array('post_type' => 'isg_job', 'posts_per_page' => 4)); if ($jobs->have_posts()) : ?>
    <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Careers', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('Work at ISG', 'isg'); ?></h2></div><a class="text-link" href="<?php echo esc_url(isg_archive_link('isg_job')); ?>"><?php esc_html_e('All vacancies', 'isg'); ?> →</a></div><div class="product-grid"><?php while ($jobs->have_posts()) : $jobs->the_post(); get_template_part('template-parts/card', null, array('post' => get_post())); endwhile; wp_reset_postdata(); ?></div></div></section>
  <?php endif; ?>
  <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Why ISG', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('Connected technology, one team', 'isg'); ?></h2></div></div><div class="why-grid">
    <?php for ($number = 1; $number <= 3; $number++) : ?><div class="why-item"><h3><?php echo esc_html(get_theme_mod('isg_why_' . $number . '_title', array(1 => 'Software and devices', 2 => 'Transaction systems', 3 => 'Deployment support')[$number])); ?></h3><p><?php echo esc_html(get_theme_mod('isg_why_' . $number . '_text', array(1 => 'Kiosk software and hardware are developed as connected solutions.', 2 => 'SkySend connects payment processing, partners and service providers.', 3 => 'The team covers system design, implementation and technical services.')[$number])); ?></p></div><?php endfor; ?>
  </div></div></section>
  <?php $partners = new WP_Query(array('post_type' => 'isg_partner', 'posts_per_page' => 12, 'orderby' => 'menu_order', 'order' => 'ASC')); if ($partners->have_posts()) : ?>
    <section class="section"><div class="wrap"><div class="section-head"><div><span class="eyebrow"><?php esc_html_e('Partners', 'isg'); ?></span><h2 class="section-title"><?php esc_html_e('Working together', 'isg'); ?></h2></div></div><div class="partner-grid"><?php while ($partners->have_posts()) : $partners->the_post(); ?><a class="partner-item" href="<?php the_permalink(); ?>"><?php if (has_post_thumbnail()) : the_post_thumbnail('medium', array('loading' => 'lazy', 'alt' => get_the_title())); else : the_title(); endif; ?></a><?php endwhile; wp_reset_postdata(); ?></div></div></section>
  <?php endif; ?>
</main>
<?php get_footer(); ?>
