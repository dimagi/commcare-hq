'use strict';

const commonDefault = require("./webpack.common");
const webpack = require('webpack');
const utils = require('./utils');

// bootstrap 3 builds off of the default common config,
// with some overrides specified below...
module.exports = Object.assign({}, commonDefault, {
    entry: utils.getEntries('b3'),

    plugins: [
        new webpack.ProvidePlugin({
            '$': 'jquery',
            'jQuery': 'jquery',  // needed for bootstrap 3 to work
        }),
    ],

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups('b3'),
        },
    },
});
