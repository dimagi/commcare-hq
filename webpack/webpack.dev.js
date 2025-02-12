/* eslint-env node */
const { merge } = require('webpack-merge');
const common = require('./webpack.common');
const b3Common = require('./webpack.b3.common');
const utils = require("./utils");

// after the Bootstrap 5 migration is complete,
// we can remove the list and just export one merged config
module.exports = [
    // this is the default webpack development config
    merge(
        common, {
            mode: 'development',
            devtool: 'eval-cheap-module-source-map',
            output: {
                filename: '[name].js',
                path: utils.WEBPACK_PATH,
                clean: true,
            },
        }),
    // this is the Bootstrap 3 development config, which
    // builds to the webpack_b3 directory and outputs
    // the manifest to manifest_b3.json
    merge(
        b3Common, {
            mode: 'development',
            devtool: 'eval-cheap-module-source-map',
            output: {
                filename: '[name].js',
                path: utils.WEBPACK_B3_PATH,
                clean: true,
            },
        }),
];
