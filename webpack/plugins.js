/* eslint-env node */
const path = require('path');
const fs = require('fs');
const appPaths = require('./appPaths');

class EntryChunksPlugin {
    /**
     * This custom plugin creates a json file (default manifest.json), which contains
     * all the Webpack Entries (aka Modules) with a list of all the required Chunks
     * needed to properly load that module without javascript errors.
     *
     * Chunks are generated based on Cache Group Chunks, which are chunked by modules
     * and vendors (npm_modules), and contain the common code shared between multiple
     * entry points that can be cached to improve subsequent page load performance.
     *
     * `get_webpack_manifest.py` in the root directory then ingests the manifest.
     * The data used by the `webpack_modules` template tag in `hq_shared_tags` to return
     * a list of modules to load in `hqwebapp/partials/webpack.html`.
     *
     * @param options (dict) — leave blank for default settings of specify filename
     */
    constructor(options = {}) {
        this.options = options;
    }

    apply(compiler) {
        compiler.hooks.emit.tapAsync('EntryChunksPlugin', (compilation, callback) => {
            const entrypoints = compilation.entrypoints;
            const manifest = {};

            entrypoints.forEach((entry, entryName) => {
                manifest[entryName] = [];

                entry.chunks.forEach((chunk) => {
                    chunk.files.forEach((file) => {
                        if (file.endsWith('.js')) {
                            manifest[entryName].push(file);
                        }
                    });
                });
            });

            fs.writeFileSync(
                path.join(appPaths.BUILD_ARTIFACTS_DIR, this.options.filename || 'manifest.json'),
                JSON.stringify(manifest, null, 2)
            );

            callback();
        });
    }
}

module.exports = {
    EntryChunksPlugin: EntryChunksPlugin,
};
