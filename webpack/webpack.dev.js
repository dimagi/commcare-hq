'use strict';

const { merge } = require('webpack-merge');
const common = require('./webpack.common');

// This is where we can set options specific to environment
module.exports = merge(common, {
    mode: 'development',
});
