/* eslint-env node */
const fs = require('fs');
const path = require('path');
const utils = require('./utils');
const { emitWarning } = require('node:process');


const getAliases = function () {
    const prodPath = path.resolve(utils.getStaticPathForApp('app_manager', 'js/vellum/'), 'main');

    let aliases = {
        // Minified version of vellum, used when VELLUM_DEBUG is False
        "jquery.vellum.prod": prodPath,

        // Supports hqAnalytics in vellum when VELLUM_DEBUG=False
        "vellum/hqAnalytics": "app_manager/js/forms/form_designer_analytics",
    };

    // Source version of vellum, used when VELLUM_DEBUG is True
    const debugDir = getDebugDir();
    if (debugDir) {
        aliases['jquery.vellum.dev'] = path.resolve(debugDir, 'src', 'main');
    } else {
        // This won't be used by application code, but it needs to resolve to a real path
        aliases['jquery.vellum.dev'] = prodPath;
    }
    return aliases;
};

const getDebugDir = function () {
    const dir = '../submodules/formdesigner';
    try {
        return fs.realpathSync(path.resolve(__dirname, dir));
    } catch (e) {
        if (e.code === "ENOENT") {
            // This is expected if VELLUM_DEBUG is False
            emitWarning("Vellum directory not found at " + path);
        } else {
            throw e;
        }
    }
    return null;
};

const getDebugConfig = function () {
    const debugDir = getDebugDir();
    if (!debugDir) {
        return null;
    }
    const configPath = path.resolve(debugDir, 'webpack/webpack.dev.js');
    try {
        return require(configPath);
    } catch (e) {
        if (e.code === "MODULE_NOT_FOUND") {
            // This is expected if VELLUM_DEBUG is False
            emitWarning("Vellum config not found at " + configPath);
            return null;
        } else {
            throw e;
        }
    }
};

const getDebugRule = function () {
    const config = getDebugConfig();
    if (!config) {
        return {};
    }
    return {
        test: getDebugDir(),    // if config exists, this dir exists
        resolve: {
            alias: config.resolve.alias,
        },
        rules: config.module.rules,
    };
};

module.exports = {
    getAliases: getAliases,
    getDebugDir: getDebugDir,
    getDebugRule: getDebugRule,
};
