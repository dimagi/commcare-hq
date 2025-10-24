/* eslint-env node */
/* eslint-disable no-useless-escape */
// MkDocs-specific version of generateDetails.js that focuses only on styleguide and essential apps

const fs = require('fs');
const path = require('path');
const appPaths = require('./appPaths');
const scanTemplates = require('./generateDetails').scanTemplates;
const getDetails = require('./generateDetails').getDetails;


// When run from the command line:
if (require.main === module) {
    if (!fs.existsSync(appPaths.BUILD_ARTIFACTS_DIR)) {
        fs.mkdirSync(appPaths.BUILD_ARTIFACTS_DIR);
    }

    const isProductionMode = process.argv.includes('--prod');
    const allAppPaths = appPaths.getAllAppPaths();

    // For MkDocs, we only want styleguide and essential dependencies
    const mkdocsApps = [
        "styleguide",      // Main styleguide components
        "hqwebapp",        // Essential HQ base functionality
    ];

    const aliases = {};
    const appsWithEntries = [];
    mkdocsApps.forEach((appName) => {
        let appDir = `${appName}/js`;
        aliases[appDir] = path.join(allAppPaths[appName], `static/${appDir}`);
        appsWithEntries.push(appName);
    });

    // Get details only for the apps we need for MkDocs
    const mkdocsDetails = getDetails(
        /{% js_entry ["']([\/\w\-]+)["'] %}/g,
        allAppPaths,
        isProductionMode,
        mkdocsApps
    );

    // Filter out problematic entries that have missing dependencies
    const filteredEntries = {};
    const problematicPatterns = [
        /spec/, // Test files
        /translations/, // Translation modules
        /reports_core/, // Reports core modules
        /case\//,  // Case modules
        /mocha/, // Test framework
        /app_manager.*manage_releases/, // App manager releases
        /cloudcare.*spec/, // Cloudcare test files
        /userreports.*configurable_report/, // UCR reports
        /userreports.*configure_report/, // UCR configuration
        /reports.*case_details/, // Reports case details
        /export.*download_export/, // Export functionality
    ];

    Object.keys(mkdocsDetails.entries).forEach(entryName => {
        const isProblematic = problematicPatterns.some(pattern => pattern.test(entryName));
        if (!isProblematic) {
            filteredEntries[entryName] = mkdocsDetails.entries[entryName];
        }
    });

    // Create essential entries that we know work
    const essentialEntries = {
        'hqwebapp/js/base': mkdocsDetails.entries['hqwebapp/js/base'],
        'styleguide/js/main': mkdocsDetails.entries['styleguide/js/main'],
        'styleguide/js/selections': mkdocsDetails.entries['styleguide/js/selections'],
        'styleguide/js/inline_edit': mkdocsDetails.entries['styleguide/js/inline_edit'],
        'styleguide/js/searching': mkdocsDetails.entries['styleguide/js/searching'],
        'styleguide/js/dates_times': mkdocsDetails.entries['styleguide/js/dates_times'],
        'styleguide/js/pagination': mkdocsDetails.entries['styleguide/js/pagination'],
        'styleguide/js/modals': mkdocsDetails.entries['styleguide/js/modals'],
        'styleguide/js/feedback': mkdocsDetails.entries['styleguide/js/feedback'],
        'styleguide/js/tables': mkdocsDetails.entries['styleguide/js/tables'],
    };

    // Only include entries that actually exist
    const validEntries = {};
    Object.keys(essentialEntries).forEach(key => {
        if (essentialEntries[key]) {
            validEntries[key] = essentialEntries[key];
        }
    });

    fs.writeFileSync(
        path.join(appPaths.BUILD_ARTIFACTS_DIR, 'details_mkdocs.json'),
        JSON.stringify({
            entries: {}, // No combined entries
            individualEntries: validEntries, // Only valid individual entries
            aliases: Object.assign(aliases, mkdocsDetails.aliases),
            appsWithEntries: [...new Set([...appsWithEntries, ...mkdocsDetails.appsWithEntries])],
            allAppPaths: allAppPaths,
        }, null, 2)
    );

    console.log(`Generated MkDocs details with ${Object.keys(validEntries).length} valid entries`);
}

module.exports = {
    getDetails: getDetails,
};
