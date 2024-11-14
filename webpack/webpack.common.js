/* eslint-env node */
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');

const aliases = {
    "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap5/'),
        'commcarehq'),
    "jquery": "jquery/dist/jquery.min",

    // todo after completing requirejs migration,
    //  remove this file and the yarn modernizr post-install step
    "modernizr": "hqwebapp/js/lib/modernizr",

    "sentry_browser": path.resolve(utils.getStaticFolderForApp('hqwebapp'),
        'sentry/js/sentry.browser.7.28.0.min'),
    "sentry_captureconsole": path.resolve(utils.getStaticFolderForApp('hqwebapp'),
        'sentry/js/sentry.captureconsole.7.28.0.min'),
    "tempusDominus": "@eonasdan/tempus-dominus",
    "ko.mapping": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/lib/knockout_plugins/'),
        'knockout_mapping.ko.min'),
};


module.exports = {
    entry: utils.getEntries(),

    module: {
        rules: [
            {
                test: /\.js$/,
                loader: 'babel-loader',
            },

            // this rule ensures that hqDefine is renamed to define AMD module
            // definition syntax that webpack understands
            {
                test: /\.js$/,
                loader: 'string-replace-loader',
                options: {
                    search: /\bhqDefine\b/g,
                    replace: 'define',
                },
            },
            {
                test: /\.js$/,
                loader: 'string-replace-loader',
                options: {
                    search: /\b(es6!)?hqwebapp\/js\/bootstrap5_loader\b/g,
                    replace: 'bootstrap5',
                },
            },

            {
                test: /modernizr\.js$/,
                loader: "webpack-modernizr-loader",
                options: {
                    "options": [
                        "setClasses",
                    ],
                    "feature-detects": [
                        "test/svg/smil",
                    ],
                },
            },

            {
                test: /sentry\.browser/,
                loader: "exports-loader",
                options: {
                    type: "commonjs",
                    exports: {
                        syntax: "single",
                        name: "Sentry",
                    },
                },
            },
        ],
    },

    plugins: [
        new webpack.ProvidePlugin({
            '$': 'jquery',
            'jQuery': 'jquery',  // needed for bootstrap to work
        }),
        new hqPlugins.EntryChunksPlugin(),
    ],

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups(),
        },
    },

    resolve: {
        alias: utils.getAllAliases(aliases),
    },
};
