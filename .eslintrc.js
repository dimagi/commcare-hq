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
        "brace-style": ["error", "1tbs", { "allowSingleLine": true }],
        "camelcase": ["error", {"properties": "never"}],
        "comma-dangle": ["warn", "always-multiline"],
        "curly": ["error"],
        "eqeqeq": ["error"],
        "func-call-spacing": ["error"],
        "indent": ["warn", 4, {"SwitchCase":1, "FunctionDeclaration": {"parameters": "first"}}],
        "linebreak-style": ["error", "unix"],
        "key-spacing": ["error"],
        "keyword-spacing": ["error"],
        "no-implicit-globals": ["error"],
        "no-irregular-whitespace": ["error"],
        "no-new-object": ["error"],
        "no-regex-spaces": ["error"],
        "no-throw-literal": ["error"],
        "no-unneeded-ternary": ["error"],
        "no-whitespace-before-property": ["error"], // match flake8 E201 and E211
        "one-var-declaration-per-line": ["error"],
        "semi": ["error", "always"],
        "space-before-function-paren": ["error", {"anonymous": "always", "named": "never", "asyncArrow": "always"}],
        "space-before-blocks": ["error"],
        "space-in-parens": ["error", "never"],
        "space-infix-ops": ["error"],   // match flake8 E225

        "eslint-dimagi/no-unblessed-new": ["error", ["Date", "Error", "FormData", "Option", "RegExp", "Clipboard", "MutationObserver"]],
    }
};
