'use strict';

const fs = require('fs');
const path = require('path');

const __BASE = path.resolve(__dirname, '..');
const TEMPLATES = 'templates';
const APPS_PATH = path.resolve(__BASE, 'corehq', 'apps');
const EX_SUBMODULES_PATH = path.resolve(__BASE, 'corehq', 'ex-submodules');
const MOTECH_PATH = path.resolve(__BASE, 'corehq', 'motech');
const CUSTOM_PATH = path.resolve(__BASE, 'custom');

const IS_PRODUCTION_MODE = process.argv.includes('--prod');

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

// A workaround for whose app folder name doesn't match the static path name (rare)
const appRenames = {
    "analytics": "analytix",
};

function hasTemplateFolder (dirEnt) {
    const templatePath = path.resolve(APPS_PATH, dirEnt.name, TEMPLATES);
    try {
        return fs.readdirSync(templatePath);
    } catch (e) {
        // throws an error if the templates directory does not exist
        return false;
    }
}

function getStandardAppPaths () {
    const paths = {};
    fs.readdirSync(APPS_PATH, {withFileTypes: true})
        .filter(dirEnt => dirEnt.isDirectory())
        .filter(hasTemplateFolder)
        .forEach(dirEnt => {
            let appName = appRenames[dirEnt.name] || dirEnt.name;
            paths[appName] = path.resolve(APPS_PATH, dirEnt.name);
        });
    return paths;
}

const allAppPaths = Object.assign(getStandardAppPaths(), nonStandardAppPaths);

// guarantee that these aliases are always generated
const aliases = {
    'hqwebapp/js': path.join(allAppPaths.hqwebapp, 'static/hqwebapp/js'),
    'notifications/js': path.join(allAppPaths.notifications, 'static/notifications/js'),
};
// guarantee that these apps are always included
const appsWithEntries = [
    "hqwebapp",
    "notifications",
];

function scanTemplates (dir, entryRegex, entries) {
    const files = fs.readdirSync(dir);

    files.forEach((file) => {
        const fullPath = path.join(dir, file);
        const stats = fs.statSync(fullPath);

        if (stats.isDirectory()) {
            scanTemplates(fullPath, entryRegex, entries); // Recursively scan subdirectories
        } else if (stats.isFile() && fullPath.endsWith('.html')) {
            let content = fs.readFileSync(fullPath, 'utf-8');
            let match;

            // Extract all matches of the {% webpack_main "path" %} tag
            while ((match = entryRegex.exec(content)) !== null) {
                let entryName = match[1];
                let folders = entryName.split('/');
                let appName = folders[0];
                let fullEntryPath = path.join(allAppPaths[appName], 'static', `${entryName}.js`);

                if (!fs.existsSync(fullEntryPath)) {
                    console.warn(`JavaScript file not found: ${fullEntryPath}`);
                    continue;
                }
                entries[entryName] = {
                    import: fullEntryPath,
                    filename: IS_PRODUCTION_MODE ? `${entryName}.[contenthash].js` : `${entryName}.js`,
                };

                let aliasName = folders.slice(0, 2).join('/');
                if (!(aliasName in aliases)) {
                    aliases[aliasName] = path.join(allAppPaths[appName], 'static', aliasName);
                }
                if (!appsWithEntries.includes(appName)) {
                    appsWithEntries.push(appName);
                }
            }
        }
    });
}

function getEntries(entryRegex) {
    const entries = {};
    for (let appName in allAppPaths) {
        let appPath = allAppPaths[appName];
        scanTemplates(appPath, entryRegex, entries);
    }
    return entries;
}

const defaultEntries = getEntries(
    /{% webpack_main ["']([\/\w\-]+)["'] %}/g
);
const b3Entries = getEntries(
    /{% webpack_main_b3 ["']([\/\w\-]+)["'] %}/g
);

fs.writeFileSync(
    path.join(__BASE, 'webpack/details.json'),
    JSON.stringify({
        entries: defaultEntries,
        b3Entries: b3Entries,
        aliases: aliases,
        appsWithEntries: appsWithEntries,
        allAppPaths: allAppPaths,
    }, null, 2)
);
