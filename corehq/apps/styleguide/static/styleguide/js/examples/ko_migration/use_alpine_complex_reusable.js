import Alpine from 'alpinejs';

import complexModel from "styleguide/js/examples/ko_migration/alpine_complex_reusable";
Alpine.data('complexExample', complexModel);

// Alternatively, you can load initial data from initialPageData here
import initialPageData from 'hqwebapp/js/initial_page_data';
Alpine.data('complexExample', () => complexModel(initialPageData.get("complex_initial_value")));

Alpine.start();
