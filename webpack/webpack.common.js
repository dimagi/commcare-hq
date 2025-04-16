/* eslint-env node */
const path = require('path');
const webpack = require('webpack');
const utils = require('./utils');
const hqPlugins = require('./plugins');

VELLUM_BASE_PATH = path.resolve(__dirname, '../submodules/formdesigner')
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
    "main.vellum.bundle": path.resolve(utils.getStaticPathForApp('app_manager', 'js/vellum/'), 'main.vellum.bundle.js'),

    // TODO: pull in Vellum config in some way other than copying
    'ckeditor': path.resolve(VELLUM_BASE_PATH, 'lib/ckeditor/ckeditor.js'),
    'ckeditor-jquery': path.resolve(VELLUM_BASE_PATH, 'lib/ckeditor/adapters/jquery.js'),
    'CryptoJS': path.resolve(VELLUM_BASE_PATH, 'lib/sha1'),
    'diff-match-patch': path.resolve(VELLUM_BASE_PATH, 'lib/diff_match_patch'),
    'save-button': path.resolve(VELLUM_BASE_PATH, 'lib', 'SaveButton.js'),
    'jquery.vellum': path.resolve(VELLUM_BASE_PATH, 'src', 'main'),
    'jstree-styles': path.resolve(VELLUM_BASE_PATH, 'node_modules/jstree/dist/themes/default/style.css'),
    'vellum': path.resolve(VELLUM_BASE_PATH, 'src'),
    'tests': path.resolve(VELLUM_BASE_PATH, 'tests'),
    'static': path.resolve(VELLUM_BASE_PATH, 'tests', 'static'),
};


module.exports = {
    entry: utils.getEntries(),

    module: {
        rules: [
            // TODO: pull in Vellum config in some way other than copying
            {
                test: /\.xml$/,
                type: 'asset/source',
            },
            {
                test: /\.html$/,
                type: 'asset/source',
            },
            {
                test: /\.tsv$/,
                type: 'asset/source',
            },
            {
                test: /\.json$/,
                type: 'json',
            },
            {
                test: /\.less$/,
                use: ["style-loader", "css-loader", "less-loader"],
            },
            {
                test: /ckeditor/,
                loader: "exports-loader",
                options: {
                    type: "commonjs",
                    exports: {
                        syntax: "single",
                        name: "CKEDITOR",
                    },
                },
            },
            {
                test: /XMLWriter/,
                loader: "exports-loader",
                options: {
                    type: "commonjs",
                    exports: {
                        syntax: "single",
                        name: "XMLWriter",
                    },
                },
            },
            // TODO: this is the end of the Vellum rules


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
