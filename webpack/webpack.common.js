/* eslint-env node */
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');
const vellumUtils = require('./vellumUtils');

const aliases = {
    "commcarehq": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/bootstrap5/'),
        'commcarehq'),
    "jquery": require.resolve('jquery'),
    "langcodes/js/langcodes": path.resolve("submodules/langcodes/static/langcodes/js/langcodes"),

    // todo after completing requirejs migration,
    //  remove this file and the yarn modernizr post-install step
    "modernizr": "hqwebapp/js/lib/modernizr",

    "nvd3/nv.d3.latest.min": "nvd3-1.8.6/build/nv.d3.min",
    "popper": "@popperjs/core/dist/cjs/popper.js",
    "sentry_browser": path.resolve(utils.getStaticFolderForApp('hqwebapp'),
        'sentry/js/sentry.browser.7.28.0.min'),
    "sentry_captureconsole": path.resolve(utils.getStaticFolderForApp('hqwebapp'),
        'sentry/js/sentry.captureconsole.7.28.0.min'),
    "tempusDominus": "@eonasdan/tempus-dominus",
    "hqwebapp/less": path.resolve(utils.getStaticPathForApp('hqwebapp', 'less')),
    "ko.mapping": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/lib/knockout_plugins/'),
        'knockout_mapping.ko.min'),
};

const vellumDebugDir = vellumUtils.getDebugDir();
module.exports = {
    entry: utils.getEntries(),

    externals: [
        function ({ context, request }, callback) {
            if (vellumDebugDir && context.startsWith(vellumDebugDir)) {
                if (request.match(/\bbootstrap\b/)) {
                    return callback(null, 'global bootstrap');
                }
            }
            callback();
        },
    ],

    module: {
        rules: [
            vellumUtils.getDebugRule(),
            {
                exclude: vellumDebugDir || [],
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
                            // Vellum is already compressed, so it does not need babel's processing
                            path.resolve(
                                __dirname, '../corehq/apps/app_manager/static/app_manager/js/vellum/main.js'),
                        ],
                    },
                    {
                        test: /\.png/,
                        type: 'asset/resource',
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
                        test: /mapbox\.js\/dist\/mapbox/,
                        loader: "exports-loader",
                        options: {
                            type: "commonjs",
                            exports: {
                                syntax: "single",
                                name: "L",
                            },
                        },
                    },
                    {
                        test: /nvd3\/nv\.d3\.min/,
                        loader: "exports-loader",
                        options: {
                            type: "commonjs",
                            exports: {
                                syntax: "single",
                                name: "nv",
                            },
                        },
                    },
                    {
                        test: /sentry\/js\/sentry/,
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
        ],
    },

    plugins: [
        new webpack.ProvidePlugin({
            '$': 'jquery',
            'jQuery': 'jquery',  // needed for bootstrap to work
            'window.jQuery': 'jquery',  // needed for some third-party libraries that depend on jQuery, such as multiselect
        }),
        new hqPlugins.EntryChunksPlugin(),
    ],

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups(),
        },
    },

    resolve: {
        alias: utils.getAllAliases(Object.assign(aliases, vellumUtils.getAliases())),
    },

    snapshot: {
        managedPaths: [
            /^node_modules\//,
        ],
    },
};
