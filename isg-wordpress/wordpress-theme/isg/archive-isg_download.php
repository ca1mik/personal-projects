<?php
get_header();
$project = isset($_GET['project']) ? sanitize_title(wp_unslash($_GET['project'])) : '';
$query_text = isset($_GET['q']) ? sanitize_text_field(wp_unslash($_GET['q'])) : '';
$per_page = isset($_GET['count']) ? (int) $_GET['count'] : 10;
$per_page = in_array($per_page, array(10, 20, 50), true) ? $per_page : 10;
$page = max(1, get_query_var('paged'));
$query_args = array('post_type' => 'isg_download', 'post_status' => 'publish', 'posts_per_page' => $per_page, 'paged' => $page, 's' => $query_text);
if ($project) {
    $query_args['tax_query'] = array(array('taxonomy' => 'isg_download_project', 'field' => 'slug', 'terms' => $project));
}
$files = new WP_Query($query_args);
$terms = get_terms(array('taxonomy' => 'isg_download_project', 'hide_empty' => true));
?>
<main id="main"><div class="page-intro"><div class="wrap"><?php isg_breadcrumbs(); ?><h1><?php esc_html_e('Downloads', 'isg'); ?></h1><p><?php esc_html_e('Find product documents, releases and technical materials.', 'isg'); ?></p></div></div>
  <section class="section"><div class="wrap">
    <div class="filters"><a class="chip<?php echo $project ? '' : ' active'; ?>" href="<?php echo esc_url(get_post_type_archive_link('isg_download')); ?>"><?php esc_html_e('All files', 'isg'); ?></a><?php if (!is_wp_error($terms)) : foreach ($terms as $term) : ?><a class="chip<?php echo $project === $term->slug ? ' active' : ''; ?>" style="--project-color:<?php echo esc_attr(get_term_meta($term->term_id, 'isg_color', true) ?: '#0166ff'); ?>" href="<?php echo esc_url(add_query_arg('project', $term->slug, get_post_type_archive_link('isg_download'))); ?>"><?php echo esc_html($term->name); ?></a><?php endforeach; endif; ?></div>
    <form class="search-row" action="<?php echo esc_url(get_post_type_archive_link('isg_download')); ?>" method="get">
      <?php if ($project) : ?><input type="hidden" name="project" value="<?php echo esc_attr($project); ?>"><?php endif; ?>
      <label class="search-field"><span class="screen-reader-text"><?php esc_html_e('Search files', 'isg'); ?></span><input type="search" name="q" value="<?php echo esc_attr($query_text); ?>" placeholder="<?php esc_attr_e('Search files', 'isg'); ?>"></label>
      <label><?php esc_html_e('Per page', 'isg'); ?> <select name="count"><?php foreach (array(10, 20, 50) as $amount) : ?><option value="<?php echo esc_attr($amount); ?>" <?php selected($per_page, $amount); ?>><?php echo esc_html($amount); ?></option><?php endforeach; ?></select></label>
      <button class="btn outline" type="submit"><?php esc_html_e('Apply', 'isg'); ?></button>
    </form>
    <p class="muted"><?php echo esc_html($files->found_posts ? sprintf(__('%1$d–%2$d of %3$d', 'isg'), ($page - 1) * $per_page + 1, min($page * $per_page, $files->found_posts), $files->found_posts) : __('0 files', 'isg')); ?></p>
    <?php if ($files->have_posts()) : ?><div class="download-grid" style="--download-columns:<?php echo esc_attr(in_array((int) get_theme_mod('isg_download_columns', 3), array(2, 3), true) ? (int) get_theme_mod('isg_download_columns', 3) : 3); ?>"><?php while ($files->have_posts()) : $files->the_post(); $url = get_post_meta(get_the_ID(), '_isg_external_url', true); $size = get_post_meta(get_the_ID(), '_isg_file_size', true); $type = get_post_meta(get_the_ID(), '_isg_file_type', true); ?>
      <article class="download-item"><div><span class="card-kicker"><?php echo esc_html($type ?: __('File', 'isg')); ?></span><h3><?php the_title(); ?></h3></div><small><?php echo esc_html(trim($type . ' · ' . $size, ' ·')); ?></small><?php if ($url) : ?><a class="text-link" href="<?php echo esc_url($url); ?>" target="_blank" rel="noopener"><?php esc_html_e('Download', 'isg'); ?> ↓</a><?php else : ?><a class="text-link" href="<?php the_permalink(); ?>"><?php esc_html_e('Details', 'isg'); ?> →</a><?php endif; ?></article>
    <?php endwhile; wp_reset_postdata(); ?></div>
    <nav class="pagination" aria-label="<?php esc_attr_e('Page navigation', 'isg'); ?>"><?php echo wp_kses_post(paginate_links(array('total' => $files->max_num_pages, 'current' => $page, 'add_args' => array('project' => $project, 'q' => $query_text, 'count' => $per_page), 'prev_text' => '←', 'next_text' => '→'))); ?></nav>
    <?php else : ?><p class="empty"><?php esc_html_e('No files match your search.', 'isg'); ?></p><?php endif; ?>
  </div></section>
</main>
<?php get_footer(); ?>
