<?php
/** Run with: wp eval-file tests/wp-seed-smoke.php --path=/path/to/wordpress */

wp_set_current_user(1);
isg_seed_data();
WP_CLI::success('Starter content is ready.');
