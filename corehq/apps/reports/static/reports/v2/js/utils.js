/**
 * todo add docstring
 */

hqDefine('reports/v2/js/utils', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';

    return {
        url: {
            endpoint: function (slug) {
                return initialPageData
                    .reverse('report_v2_endpoint')
                    .replace('slug', slug);
            },
        },
    };
});
