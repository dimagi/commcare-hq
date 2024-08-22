'use strict';

const fs = require('fs');
const path = require('path');

const __BASE = path.resolve(__dirname, '..');
const TEMPLATES_DIR = 'templates';
const APPS_PATH = path.resolve(__BASE, 'corehq', 'apps');
const EX_SUBMODULES_PATH = path.resolve(__BASE, 'corehq', 'ex-submodules');
const MOTECH_PATH = path.resolve(__BASE, 'corehq', 'motech');
const CUSTOM_PATH = path.resolve(__BASE, 'custom');

const nonStandardAppPaths = {
    "case": path.resolve(EX_SUBMODULES_PATH, 'casexml', 'apps', 'case'),
    "soil": path.resolve(EX_SUBMODULES_PATH, 'soil'),
    "motech": MOTECH_PATH,
    // motech apps:
    "dhis2": path.resolve(MOTECH_PATH, 'dhis2'),
    "generic_inbound": path.resolve(MOTECH_PATH, 'generic_inbound'),
    "openmrs": path.resolve(MOTECH_PATH, 'openmrs'),
    "repeaters": path.resolve(MOTECH_PATH, 'repeaters'),
    // custom apps:
    "champ": path.resolve(CUSTOM_PATH, 'champ'),
    "inddex": path.resolve(CUSTOM_PATH, 'inddex'),
    "mc": path.resolve(CUSTOM_PATH, 'reports', 'mc'),
    "up_nrhm": path.resolve(CUSTOM_PATH, 'up_nrhm'),
};

// workaround for apps that have different folder names in the static directory (rare)
const appRenames = {
    "analytics": "analytix",
};

const hasTemplateFolder = function (dirEnt) {
    const templatePath = path.resolve(APPS_PATH, dirEnt.name, TEMPLATES_DIR);
    try {
        return fs.readdirSync(templatePath);
    } catch (e) {
        // throws an error if the templates directory does not exist
        return false;
    }
};

const getStandardAppPaths = function () {
    const paths = {};
    fs.readdirSync(APPS_PATH, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(hasTemplateFolder)
        .forEach(dirEnt => {
            let appName = appRenames[dirEnt.name] || dirEnt.name;
            paths[appName] = path.resolve(APPS_PATH, dirEnt.name);
        });
    return paths;
};

const getAllAppPaths = function () {
    return Object.assign(getStandardAppPaths(), nonStandardAppPaths);
};

module.exports = {
    getAllAppPaths: getAllAppPaths,
    TEMPLATES_DIR: TEMPLATES_DIR,
};
