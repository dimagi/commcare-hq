'use strict';

hqDefine("prototype/js/webpack/bootstrap3_amd",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    "commcarehq",  // IMPORTANT :: this has to be included with any Bootstrap 3 entry point
], function ($, ko, _, initialPageData) {
    /**
     * This is an (HQ)AMD-formatted module, intended to be used with js_entry as follows:
     * {% js_entry_b3 "prototype/js/webpack/bootstrap3_amd" %}
     *
     * It serves as a test to see that Webpack is working fine with this type of module
     * and is an example of what a quick migration of an existing requirejs module might
     * look like.
     *
     * The most important difference between a requirejs module and a webpack module of this type
     * is that the webpack module requires that the "commcarehq" dependency is included
     * in the list of dependencies above. Otherwise, everything else should function
     * identically to the requirejs module, provided the appropriate shims are in place
     * in the Webpack config for special dependencies.
     *
     * For details on creating new shims, see: https://webpack.js.org/loaders/exports-loader/
     *
     * This file can be used to test such shims, webpack optimizations, or to carry out
     * preliminary Webpack-related tests in production environments.
     *
     */
    console.log("\n\nBelow are some basic tests to see that this Webpack module is working as expected:\n\n");
    console.log("\nDid jQuery load?");
    console.log($);
    console.log("\nDid knockout load?");
    console.log(ko);
    console.log("\nDid underscore load?");
    console.log(_);
    console.log("\nIs initialPageData retrievable?");
    console.log(initialPageData.get('test_initial'));
    console.log("\nAre translations working?");
    console.log(gettext("yes"));
    console.log("\nIs bootstrap 5 working?");
    console.log("click around the page and see that dropdowns work...");
    console.log("\n\n");
});
