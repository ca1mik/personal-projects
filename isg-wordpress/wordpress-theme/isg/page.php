<?php get_header(); ?>
<main id="main">
  <?php while (have_posts()) : the_post(); ?>
    <div class="page-intro"><div class="wrap"><?php isg_breadcrumbs(); ?><h1><?php the_title(); ?></h1><?php if (has_excerpt()) : ?><p><?php echo esc_html(get_the_excerpt()); ?></p><?php endif; ?></div></div>
    <div class="wrap entry-content page-content">
      <?php the_content();
      $slug = get_post_field('post_name', get_the_ID());
      if ($slug === 'company') :
          $children = get_pages(array('parent' => get_the_ID(), 'sort_column' => 'menu_order,post_title'));
          if ($children) : ?><div class="industry-grid"><?php foreach ($children as $child) : ?><article class="industry-card"><div class="industry-card-body"><h2><?php echo esc_html(get_the_title($child)); ?></h2><a class="text-link" href="<?php echo esc_url(get_permalink($child)); ?>"><?php esc_html_e('Explore', 'isg'); ?> &#8594;</a></div></article><?php endforeach; ?></div><?php endif;
      elseif ($slug === 'support') : ?>
          <div class="industry-grid"><article class="industry-card"><div class="industry-card-body"><h2><?php esc_html_e('Downloads', 'isg'); ?></h2><a class="text-link" href="<?php echo esc_url(isg_archive_link('isg_download')); ?>"><?php esc_html_e('Browse files', 'isg'); ?> &#8594;</a></div></article><article class="industry-card"><div class="industry-card-body"><h2><?php esc_html_e('Feedback', 'isg'); ?></h2><a class="text-link" href="<?php echo esc_url(home_url('/support/feedback/')); ?>"><?php esc_html_e('Contact support', 'isg'); ?> &#8594;</a></div></article></div>
      <?php elseif ($slug === 'licenses') :
          $documents = get_posts(array('post_type' => 'isg_download', 'numberposts' => -1, 'tax_query' => array(array('taxonomy' => 'isg_download_project', 'field' => 'slug', 'terms' => 'company'))));
          if ($documents) : ?><div class="catalog-grid"><?php foreach ($documents as $document) : get_template_part('template-parts/card', null, array('post' => $document)); endforeach; ?></div><?php endif;
      elseif ($slug === 'partnership') :
          $partners = get_posts(array('post_type' => 'isg_partner', 'numberposts' => -1, 'orderby' => 'menu_order', 'order' => 'ASC'));
          if ($partners) : ?><h2><?php esc_html_e('Our partners', 'isg'); ?></h2><div class="partner-grid"><?php foreach ($partners as $partner) : ?><a class="partner-item" href="<?php echo esc_url(get_permalink($partner)); ?>"><?php echo get_the_post_thumbnail($partner, 'medium', array('alt' => get_the_title($partner))) ?: esc_html(get_the_title($partner)); ?></a><?php endforeach; ?></div><?php endif;
      elseif ($slug === 'careers') :
          $jobs = get_posts(array('post_type' => 'isg_job', 'numberposts' => -1));
          if ($jobs) : ?><h2><?php esc_html_e('Open roles', 'isg'); ?></h2><div class="catalog-grid"><?php foreach ($jobs as $job) : get_template_part('template-parts/card', null, array('post' => $job)); endforeach; ?></div><?php endif;
      elseif (in_array($slug, array('contacts', 'feedback'), true)) :
          $email = get_theme_mod('isg_email', 'info@isg.dev');
          $telegram = get_theme_mod('isg_telegram', 'https://t.me/infsysgroup');
          ?><div class="contact-grid"><div class="contact-item"><strong><?php esc_html_e('Email', 'isg'); ?></strong><a href="mailto:<?php echo esc_attr(antispambot($email)); ?>"><?php echo esc_html(antispambot($email)); ?></a></div><div class="contact-item"><strong>Telegram</strong><a href="<?php echo esc_url($telegram); ?>" target="_blank" rel="noopener">@infsysgroup</a></div><div class="contact-item"><strong><?php esc_html_e('Sales', 'isg'); ?></strong><a href="mailto:<?php echo esc_attr(antispambot(get_theme_mod('isg_sales_email', 'sales@isg.dev'))); ?>"><?php echo esc_html(antispambot(get_theme_mod('isg_sales_email', 'sales@isg.dev'))); ?></a></div></div><?php
      endif; ?>
    </div>
  <?php endwhile; ?>
</main>
<?php get_footer(); ?>
