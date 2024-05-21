'use strict';

const path = require('path');
const webpack = require('webpack');
const fs = require('fs');

//Just to help us with directories and folders path
const __base = path.resolve(__dirname, '..');

const BUNDLE_SUFFIX = '.main.js';


const getAppJsName = function (appName) {
    const appJsNames = {
        "analytics": "analytix",
    };
    return appJsNames[appName] || appName;
};

const getStaticPathForApp = function (appName, directory) {
    directory = directory || "";
    const staticFolder = path.resolve(__base, 'corehq', 'apps', appName, 'static');

    return path.resolve(staticFolder, getAppJsName(appName), directory);
};

const isEntryPoint = function (dirEntry) {
    const jsPath = getStaticPathForApp(dirEntry.name, 'js');
    try {
        return fs.readdirSync(jsPath);
    } catch (e) {
        // throws an error if the js directory does not exist
        return false;
    }
};

const getEntriesForApp = function (appName, directory) {
    directory = directory || 'js';
    const jsPath = getStaticPathForApp(appName, directory);
    let entries = {};
    fs.readdirSync(jsPath, {withFileTypes: true})
        .forEach(dirEnt => {
            if (dirEnt.isFile() && dirEnt.name.endsWith(BUNDLE_SUFFIX)) {
                const filename = dirEnt.name.slice(0, -BUNDLE_SUFFIX.length);
                const directoryName = directory.replace('/', '_');
                const fullName = `${appName}_${directoryName}_${filename}`;
                entries[fullName] = {
                    import: path.resolve(dirEnt.path, dirEnt.name),
                    filename: `${getAppJsName(appName)}/${directory}/${filename}.js`,
                };
            } else if (dirEnt.isDirectory()) {
                const nextDirectory = `${directory}/${dirEnt.name}`;
                entries = Object.assign(entries, getEntriesForApp(appName, nextDirectory));
            }
        });
    return entries;
};


const getEntries = function () {
    const appsPath = path.resolve(__base, 'corehq', 'apps');
    let entries = {};
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(isEntryPoint)
        .forEach(dirEnt => {
            entries = Object.assign(entries, getEntriesForApp(dirEnt.name));
        });
    return entries;
};

const getAliases = function (directory) {
    directory = directory || 'js';
    const appsPath = path.resolve(__base, 'corehq', 'apps');
    const aliases = {
        "jquery": "jquery/dist/jquery.min",
        "ko.mapping": path.resolve(getStaticPathForApp('hqwebapp', 'js/lib/knockout_plugins/'),
            'knockout_mapping.ko.min'),
    };
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(isEntryPoint)
        .forEach(dirEnt => {
            aliases[`${getAppJsName(dirEnt.name)}/${directory}`] = getStaticPathForApp(dirEnt.name, directory);
        });
    return aliases;
};


module.exports = {
    entry: getEntries(),

    output: {
        filename: '[name].js',
        path: path.resolve(__base, 'staticfiles/webpack'),
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
                    search: /\bes6!hqwebapp\/js\/bootstrap5_loader\b/g,
                    replace: 'bootstrap5',
                },
            },
        ],
    },

    plugins: [
        new webpack.ProvidePlugin({
            '$': 'jquery',
        }),
    ],

    resolve: {
        alias: getAliases(),
    },
};
