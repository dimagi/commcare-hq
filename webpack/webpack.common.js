/* eslint-env node */
const fs = require('fs');
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');
const { merge } = require('webpack-merge');
const { emitWarning } = require('node:process');

VELLUM_DEBUG_PATH = fs.realpathSync(path.resolve(__dirname, '../submodules/formdesigner'));
VELLUM_DEBUG_CONFIG_PATH = path.resolve(VELLUM_DEBUG_PATH, 'webpack/webpack.dev.js');
let vellumConfig = {},
    vellumAliases = [],
    vellumRules = [];
try {
    vellumConfig = require(VELLUM_DEBUG_CONFIG_PATH);
    vellumAliases = vellumConfig.resolve.alias;
    vellumRules = vellumConfig.module.rules;
} catch (e) {
    if (e.code === "MODULE_NOT_FOUND") {
        // do nothing, vellum config isn't necessary if VELLUM_DEBUG is false
        emitWarning("Vellum config not found at " + VELLUM_DEBUG_CONFIG_PATH);
    } else {
        throw e;
    }
}

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
    "ko.mapping": path.resolve(utils.getStaticPathForApp('hqwebapp', 'js/lib/knockout_plugins/'),
        'knockout_mapping.ko.min'),

    // Minified version of vellum, used when VELLUM_DEBUG is False
    "jquery.vellum.prod": path.resolve(utils.getStaticPathForApp('app_manager', 'js/vellum/'), 'main'),

    "jquery.vellum.dev": path.resolve(VELLUM_DEBUG_PATH, 'src', 'main'),
};

module.exports = {
    entry: utils.getEntries(),

    module: {
        rules: [
            {
                test: VELLUM_DEBUG_PATH,
                resolve: {
                    alias: vellumAliases,
                },
                rules: vellumRules,
            },
            {
                exclude: VELLUM_DEBUG_PATH,
                rules: [
                    {
                        test: /\.css$/i,
                        use: ["style-loader", "css-loader"],
                    },
                    {
                        test: /\.js$/,
                        loader: 'babel-loader',
                        exclude: /node_modules/,
                    },
                    {
                        test: /\.png/,
                        type: 'asset/resource',
                    },

                    // this rule ensures that hqDefine is renamed to define AMD module
                    // definition syntax that webpack understands
                    {
                        test: /\.js$/,
                        loader: 'string-replace-loader',
                        exclude: /node_modules/,
                        options: {
                            search: /\bhqDefine\b/g,
                            replace: 'define',
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
                ]
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
        alias: utils.getAllAliases(aliases),
    },

    snapshot: {
        managedPaths: [
            /^node_modules\//,
        ],
    },
};
