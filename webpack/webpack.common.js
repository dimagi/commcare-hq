'use strict';

const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');

const aliases = {
    "jquery": "jquery/dist/jquery.min",
    "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap5/'),
        'commcarehq'),
    "commcarehq_b3": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap3/'),
        'commcarehq'),

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

    output: {
        filename: '[name].js',
        path: utils.getStaticfilesPath(),
        clean: true,
    },

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
            'jQuery': 'jquery', // needed for bootstrap 3 to work
        }),
    ],

    optimization: {
        splitChunks: {
            cacheGroups: {
                hqwebapp: {
                    test: /[\\/]hqwebapp[\\/]js[\\/]/,
                    name: 'hqwebapp',
                    chunks: 'all',
                    minSize: 0, // Include even small modules
                },
                // hqwebapp: {
                //     test: /\/hqwebapp\/js\/(?!.*(bootstrap3|bootstrap5)\/).*\.js$/,
                //     name: 'hqwebapp',
                //     chunks: 'all',
                //     minSize: 0, // Include even small modules
                // },
                // hqwebappBootstrap5: {
                //     test: /\/hqwebapp\/js\/.*bootstrap5\/.*\.js$/,
                //     name: 'hqwebapp-bootstrap5',
                //     chunks: 'all',
                //     minSize: 0, // Include even small modules
                // },
                // hqwebappBootstrap3: {
                //     test: /\/hqwebapp\/js\/.*bootstrap3\/.*\.js$/,
                //     name: 'hqwebapp-bootstrap3',
                //     chunks: 'all',
                //     minSize: 0, // Include even small modules
                // },
                prototype: {
                    test: /[\\/]prototype[\\/]js[\\/]/,
                    name: 'prototype',
                    chunks: 'all',
                    minSize: 0, // Include even small modules
                },
                vendors: {
                    test: /[\\/]node_modules[\\/]/,
                    name: 'vendors',
                    chunks: 'all',
                },
            },
        },
    },

    resolve: {
        alias: utils.getAllAliases(aliases),
    },
};
