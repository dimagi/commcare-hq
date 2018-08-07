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
        "define": false,
        "hqDefine": false,
        "hqImport": false,
        "hqRequire": false,
        "requirejs": false,
        "gettext": false,
        "ngettext": false,
        "assert": false,
        "sinon": false,
        "$": false,
        "ko": false,
        "_": false,
        "L": true,
        "it": false,
        "describe": false,
        "beforeEach": false,
        "nv": false,
        "d3": false,
    },

    "plugins": [
        "eslint-dimagi",
    ],

    // http://eslint.org/docs/rules/
    // http://eslint.org/docs/user-guide/configuring#configuring-rules
    "rules": {
        // First option can be off, warn, or error
        "camelcase": ["error", {"properties": "never"}],
        "comma-dangle": ["warn", "always-multiline"],
        "eqeqeq": ["error"],
        "indent": ["warn", 4, {"SwitchCase":1}],
        "linebreak-style": ["error", "unix"],
        "semi": ["error", "always"],
        "no-new-object": ["error"],
        "no-unneeded-ternary": ["error"],
        "no-throw-literal": ["error"],
        "no-implicit-globals": ["error"],

        "eslint-dimagi/no-unblessed-new": ["error", ["Date", "Error", "RegExp", "Clipboard"]],
    }
};
