'use strict';

const path = require("path");
const fs = require("fs");

const __BASE = path.resolve(__dirname, '..');
const SETTINGS_FILE = path.resolve(__dirname, 'settings.json');
const DETAILS_FILE = path.resolve(__dirname, 'details.json');

const fetchJsonDataOrDefault = function (filePath, defaultData) {
    let fetchedData = defaultData;
    if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        fetchedData = JSON.parse(content);
    }
    return fetchedData;
};

const DETAILS = fetchJsonDataOrDefault(DETAILS_FILE, {});
const SETTINGS = fetchJsonDataOrDefault(SETTINGS_FILE, {
    staticfilesPath: path.resolve(__BASE, 'staticfiles'),
});
const WEBPACK_PATH = path.join(SETTINGS.staticfilesPath, 'webpack');
const WEBPACK_B3_PATH = path.join(SETTINGS.staticfilesPath, 'webpack_b3');

const getStaticFolderForApp = function (appName) {
    const appPath = DETAILS.allAppPaths[appName];
    if (!appPath) {
        console.warn(`No path found for ${appName}`);
    }
    return path.join(appPath, 'static');
};

const getStaticPathForApp = function (appName, directory) {
    directory = directory || "";
    const staticFolder = getStaticFolderForApp(appName);
    return path.resolve(staticFolder, appName, directory);
};

const getEntries = function (otherEntry) {
    const otherEntries = {
        'b3': DETAILS.b3Entries,
    };
    return otherEntries[otherEntry] || DETAILS.entries;
};

const getAllAliases = function (aliases) {
    return Object.assign(aliases, DETAILS.aliases);
};

const getCacheGroups = function () {
    const cacheGroups = {
        common: {
            name: 'common',
            chunks: 'all',
            minChunks: 2,
            priority: 1,
        },
        vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendor',
            chunks: 'all',
            priority: 1,
        },
    };

    DETAILS.appsWithEntries.forEach(appName => {
        const testExp = new RegExp("[\\\\/]" + appName + "[\\\\/]js[\\\\/]");
        cacheGroups[appName] = {
            test: testExp,
            name: `${appName}/${appName}.bundle`,
            chunks: 'all',
            minChunks: 1,
            priority: 0,
        };
    });
    return cacheGroups;
};

module.exports = {
    WEBPACK_PATH: WEBPACK_PATH,
    WEBPACK_B3_PATH: WEBPACK_B3_PATH,
    getStaticFolderForApp: getStaticFolderForApp,
    getStaticPathForApp: getStaticPathForApp,
    getEntries: getEntries,
    getAllAliases: getAllAliases,
    getCacheGroups: getCacheGroups,
};
