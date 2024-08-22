/* eslint-env node */
const commonDefault = require("./webpack.common");
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
        }),
        new hqPlugins.EntryChunksPlugin({
            filename: 'manifest_b3.json',
        }),
    ],

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups('b3'),
        },
    },
});
