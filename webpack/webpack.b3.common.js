/* eslint-env node */
const commonDefault = require("./webpack.common");
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');

// bootstrap 3 builds off of the default common config,
// with some overrides specified below...
module.exports = Object.assign({}, commonDefault, {
    entry: utils.getEntries('b3'),

    plugins: [
        new webpack.ProvidePlugin({
            '$': 'jquery',
            'jQuery': 'jquery',  // needed for bootstrap 3 to work
            'window.jQuery': 'jquery',  // needed for some third-party libraries that depend on jQuery, such as multiselect
        }),
        new hqPlugins.EntryChunksPlugin({
            filename: 'manifest_b3.json',
        }),

        // Supports hqAnalytics in vellum when VELLUM_DEBUG=True
        new webpack.NormalModuleReplacementPlugin(
            /hqAnalytics\.js/,
            path.resolve(utils.getStaticPathForApp('app_manager', 'js/forms/'), 'form_designer_analytics.js'),
        ),
    ],

    resolve: {
        alias: Object.assign({}, commonDefault.resolve.alias, {
            "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap3/'), 'commcarehq'),
            "datatables": "datatables.net/js/jquery.dataTables",
            "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
            "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        }),

        // Needed for js-xpath in app manager
        fallback: {
            "path": false,
            "fs": false,
        },
    },

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups('b3'),
        },
    },
});
