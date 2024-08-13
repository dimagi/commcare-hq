'use strict';

const path = require("path");
const fs = require("fs");

const __BASE = path.resolve(__dirname, '..');
const BUNDLE_SUFFIX = '.main.js';

const getStaticfilesPath = function () {
    return path.resolve(__BASE, 'staticfiles/webpack');
};

const getAppJsName = function (appName) {
    const appJsNames = {
        "analytics": "analytix",
    };
    return appJsNames[appName] || appName;
};

const getStaticFolderForApp = function (appName) {
    return path.resolve(__BASE, 'corehq', 'apps', appName, 'static');
};

const getStaticPathForApp = function (appName, directory) {
    directory = directory || "";
    const staticFolder = getStaticFolderForApp(appName);

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
    const appsPath = path.resolve(__BASE, 'corehq', 'apps');
    let entries = {};
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(isEntryPoint)
        .forEach(dirEnt => {
            entries = Object.assign(entries, getEntriesForApp(dirEnt.name));
        });

    return entries;
};

const addAppAliases = function (aliases, directory) {
    const appsPath = path.resolve(__BASE, 'corehq', 'apps');
    directory = directory || 'js';
    fs.readdirSync(appsPath, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(isEntryPoint)
        .forEach(dirEnt => {
            aliases[`${getAppJsName(dirEnt.name)}/${directory}`] = getStaticPathForApp(dirEnt.name, directory);
        });
};

const getAllAliases = function (aliases) {
    addAppAliases(aliases);  // todo other directories outside of js?
    return aliases;
};


module.exports = {
    getStaticfilesPath: getStaticfilesPath,
    getStaticFolderForApp: getStaticFolderForApp,
    getStaticPathForApp: getStaticPathForApp,
    getEntries: getEntries,
    getAllAliases: getAllAliases,
};
