/**
 * todo add docstring
 */

hqDefine('reports/v2/js/utils', [
    'jquery',
    'knockout',
    'underscore', // can we switch to lodash?
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';

    var module = {};
    console.log('hai utils');


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
