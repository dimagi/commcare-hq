/* eslint-env node */
const { merge } = require('webpack-merge');
const common = require('./webpack.common');
const b3Common = require('./webpack.b3.common');
const utils = require("./utils");


// After the Bootstrap 5 migration is complete,
// we can remove the list and just export one merged config
module.exports = [
    // this is the default webpack production config
    merge(
        common, {
            mode: 'production',
            devtool: 'source-map',
            performance: {
                // for now we'll disable bundle size warnings until we
                // are ready to implement recommended optimizations
                hints: false,
            },
            output: {
                filename: '[name].[contenthash].js', // cache-busting
                path: utils.WEBPACK_PATH,
                clean: true,
            },
        }),
    // this is the Bootstrap 3 production config, which
    // builds to the webpack_b3 directory
    merge(
        b3Common, {
            mode: 'production',
            devtool: 'source-map',
            performance: {
                hints: false,
            },
            output: {
                filename: '[name].[contenthash].js',
                path: utils.WEBPACK_B3_PATH,
                clean: true,
            },
        }),
];
