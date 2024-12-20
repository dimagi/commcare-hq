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
    ],

    resolve: {
        alias: Object.assign({}, commonDefault.resolve.alias, {
            "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap3/'), 'commcarehq'),
            "datatables": "datatables.net/js/jquery.dataTables.min",
            "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        }),
    },

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups('b3'),
        },
    },
});
