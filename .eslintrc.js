// http://eslint.org/
module.exports = {
    "extends": "eslint:recommended",

    // http://eslint.org/docs/user-guide/configuring#specifying-environments
    "env": {
        "browser": true,
    },

    // http://eslint.org/docs/user-guide/configuring#specifying-globals
    "globals": {
        // false means it shouldn't be overwritten
        "hqDefine": false,
        "hqImport": false,
        "gettext": false,
        "$": false,
        "ko": false,
        "_": false,
        "ga_track_event": false,
    },

    // http://eslint.org/docs/rules/
    // http://eslint.org/docs/user-guide/configuring#configuring-rules
    "rules": {
        // First option can be off, warn, or error
        "indent": ["warn", 4],
        "linebreak-style": ["error", "unix"],
        "eqeqeq": ["error"],
        "semi": ["error", "always"],
    }
};
