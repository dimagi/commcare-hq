'use strict';

const fs = require('fs');
const path = require('path');
const appPaths = require('./appPaths');

const scanTemplates = function (dir, entryRegex, allAppPaths, details, isProdMode) {
    const files = fs.readdirSync(dir);

    files.forEach((file) => {
        let fullPath = path.join(dir, file);
        let stats = fs.statSync(fullPath);

        if (stats.isDirectory()) {
            // Make sure we recursively scan subdirectories
            scanTemplates(fullPath, entryRegex, allAppPaths, details, isProdMode);
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
                details.entries[entryName] = {
                    import: fullEntryPath,
                    // for cache-busting in production:
                    filename: isProdMode ? `${entryName}.[contenthash].js` : `${entryName}.js`,
                };

                let aliasName = folders.slice(0, 2).join('/');
                if (!(aliasName in details.aliases)) {
                    details.aliases[aliasName] = path.join(allAppPaths[appName], 'static', aliasName);
                }
                if (!details.appsWithEntries.includes(appName)) {
                    details.appsWithEntries.push(appName);
                }
            }
        }
    });
};

const getDetails = function (entryRegex, allAppPaths, isProdMode) {
    const details = {
        entries: {},
        aliases: {},
        appsWithEntries: [],
    };
    for (let appName in allAppPaths) {
        scanTemplates(
            path.join(allAppPaths[appName], appPaths.TEMPLATES_DIR),
            entryRegex,
            allAppPaths,
            details,
            isProdMode
        );
    }
    return details;
};

// When run from the command line:
if (require.main === module) {
    const isProductionMode = process.argv.includes('--prod');
    const allAppPaths = appPaths.getAllAppPaths();

    // guarantee that these aliases are always generated
    const aliases = {
        'analytix/js': path.join(allAppPaths.analytix, 'static/analytix/js'),
        'hqwebapp/js': path.join(allAppPaths.hqwebapp, 'static/hqwebapp/js'),
        'notifications/js': path.join(allAppPaths.notifications, 'static/notifications/js'),
    };

    // guarantee that these apps are always included
    const appsWithEntries = [
        "analytix",
        "hqwebapp",
        "notifications",
    ];

    // This splits the builds into bootstrap 5 and bootstrap 3 versions
    const defaultDetails = getDetails(
        /{% webpack_main ["']([\/\w\-]+)["'] %}/g,
        allAppPaths,
        isProductionMode
    );
    const b3Details = getDetails(
        /{% webpack_main_b3 ["']([\/\w\-]+)["'] %}/g,
        allAppPaths,
        isProductionMode
    );

    fs.writeFileSync(
        path.resolve(__dirname, 'details.json'),
        JSON.stringify({
            entries: defaultDetails.entries,
            b3Entries: b3Details.entries,
            aliases: Object.assign(
                aliases,
                defaultDetails.aliases,
                b3Details.aliases
            ),
            appsWithEntries: Object.assign(
                appsWithEntries,
                defaultDetails.appsWithEntries,
                b3Details.appsWithEntries
            ),
            allAppPaths: allAppPaths,
        }, null, 2)
    );
}

module.exports = {
    getDetails: getDetails,
};
