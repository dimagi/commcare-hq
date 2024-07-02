const path = require('path');
const fs = require('fs');

const BUNDLE_SUFFIX = 'Main.js';

function hasReactCode(dirEntry) {
    const reactPath = getReactPathForApp(dirEntry.name);
    try {
        return fs.readdirSync(reactPath).some(name => name.endsWith(BUNDLE_SUFFIX));
    } catch (e) {
        return false;
    }
}

function getReactPathForApp(app) {
    return path.resolve(__dirname, 'corehq', 'apps', app, 'static', app, 'js', 'react');
}

function getEntriesForApp(app) {
    const reactPath = getReactPathForApp(app);
    const entries = {};
    fs.readdirSync(reactPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isFile())
        .filter(dirEnt => dirEnt.name.endsWith(BUNDLE_SUFFIX))
        .forEach(dirEnt => {
            const filename = dirEnt.name.slice(0, -BUNDLE_SUFFIX.length);
            const fullName = `${app}_${filename}`;
            entries[fullName] = {
                import: path.resolve(dirEnt.path, dirEnt.name),
                filename: `${app}/${filename}.js`,
            };
        });

    return entries;
}

function getAppAliases() {
    const appsPath = path.resolve(__dirname, 'corehq', 'apps');
    const aliases = {};
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(hasReactCode)
        .forEach(dirEnt => {
            aliases[`HQ/${dirEnt.name}`] = getReactPathForApp(dirEnt.name);
        });

    return aliases;
}

function getDynamicReactApps() {
    const appsPath = path.resolve(__dirname, 'corehq', 'apps');
    let reactEntries = {};
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(hasReactCode)
        .forEach(dirEnt => {
            reactEntries = Object.assign(reactEntries, getEntriesForApp(dirEnt.name));
        });

    return reactEntries;
}

function getEntries() {
    const customEntries = {
        'reactExamples': './frontend/reactExamples.js',
        'mobileWorkers2': './corehq/apps/users/static/users/js/react_test.js',
    };
    return Object.assign(getDynamicReactApps(), customEntries);
}

module.exports = {
    entry: getEntries(),
    output: {
        filename: '[name].js',
        path: path.resolve(__dirname, './static_react'),
    },
    module: {
        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules/,
                loader: 'babel-loader',
                options: { presets: ['@babel/preset-env', '@babel/preset-react'] },
            },
        ],
    },
    resolve: {
        alias: getAppAliases(),
    },
};