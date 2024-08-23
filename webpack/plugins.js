const path = require('path');
const fs = require('fs');

class EntryChunksPlugin {
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
                path.resolve(__dirname, this.options.filename || 'manifest.json'),
                JSON.stringify(manifest, null, 2)
            );

            callback();
        });
    }
}

module.exports = {
    EntryChunksPlugin: EntryChunksPlugin,
};
