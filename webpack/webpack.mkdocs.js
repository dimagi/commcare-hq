/* eslint-env node */
const { merge } = require('webpack-merge');
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');

const __BASE = path.resolve(__dirname, '..');

// Read the MkDocs-specific details file
const mkdocsDetails = require('./_build/details_mkdocs.json');

// Create common configuration similar to webpack.common.js but for MkDocs
const mkdocsCommon = {
    // Use individual entries instead of combined entries for separate asset generation
    entry: mkdocsDetails.individualEntries,

    resolve: {
        alias: Object.assign({}, {
            "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap5/'), 'commcarehq'),
            "jquery": require.resolve('jquery'),
            "knockout": require.resolve('knockout'),
            "underscore": require.resolve('underscore'),
            "bootstrap": require.resolve('bootstrap'),
            "bootstrap5": require.resolve('bootstrap5'),
            "langcodes/js/langcodes": path.resolve("submodules/langcodes/static/langcodes/js/langcodes"),
            "modernizr": "hqwebapp/js/lib/modernizr",
            "nvd3/nv.d3.latest.min": "nvd3-1.8.6/build/nv.d3.min",
            "popper": "@popperjs/core/dist/cjs/popper.js",
            "sentry_browser": path.resolve(utils.getStaticFolderForApp('hqwebapp'), 'sentry/js/sentry.browser.7.28.0.min'),
            "sentry_captureconsole": path.resolve(utils.getStaticFolderForApp('hqwebapp'), 'sentry/js/sentry.captureconsole.7.28.0.min'),
            "tempusDominus": "@eonasdan/tempus-dominus",
            "hqwebapp/less": path.resolve(utils.getStaticPathForApp('hqwebapp', 'less')),
            "ko.mapping": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/lib/knockout_plugins/'), 'knockout_mapping.ko.min'),
        }, mkdocsDetails.aliases),
        modules: [
            'node_modules',
            path.resolve(__BASE, 'corehq'),
        ],
    },

    module: {
        rules: [
            {
                test: /\.css$/i,
                use: ["style-loader", "css-loader"],
            },
            {
                test: /\.less$/,
                use: ["style-loader", "css-loader", "less-loader"],
            },
            {
                test: /\.js$/,
                loader: 'babel-loader',
                exclude: [
                    /node_modules/,
                    path.resolve(__dirname, '../corehq/apps/app_manager/static/app_manager/js/vellum/main.js'),
                ],
            },
            {
                test: /\.png$/,
                type: 'asset/resource',
            },
            {
                test: /modernizr\.js$/,
                loader: "webpack-modernizr-loader",
                options: {
                    "options": ["setClasses"],
                    "feature-detects": ["test/svg/smil"],
                },
            },
        ],
    },

    plugins: [
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            'window.jQuery': 'jquery',
        }),
        new hqPlugins.EntryChunksPlugin({
            filename: 'manifest_mkdocs.json',
        }),
    ],

    optimization: {
        splitChunks: {
            chunks: 'all',
            cacheGroups: {
                vendor: {
                    test: /[\\/]node_modules[\\/]/,
                    name: 'vendor',
                    chunks: 'all',
                    priority: 10,
                },
                common: {
                    name: 'common',
                    minChunks: 2,
                    chunks: 'all',
                    priority: 5,
                    reuseExistingChunk: true,
                },
            },
        },
    },

    performance: {
        hints: false,
    },
};

// Export production-like configuration for MkDocs
module.exports = merge(mkdocsCommon, {
    mode: 'production',
    devtool: 'source-map',
    output: {
        filename: '[name].[contenthash].js',
        path: path.resolve(__BASE, 'staticfiles', 'webpack_mkdocs'),
        clean: true,
        publicPath: '/staticfiles/webpack_mkdocs/',
    },
});
