// https://eslint.org/docs/latest/use/configure/configuration-files
'use strict';

const js = require('@eslint/js');
const globals = require('globals');

module.exports = [
    {
        ignores: ['corehq/apps/app_manager/static/app_manager/js/vellum/**', '**/_design/**/*.js', 'eslint/**', 'eslint.config.js'],
    },

    js.configs.recommended,

    {
        // https://eslint.org/docs/latest/use/configure/language-options
        languageOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
            globals: {
                ...globals.browser,
                ...globals.es2015,

                // https://eslint.org/docs/latest/use/configure/language-options#specify-globals
                // "readonly" replaces false, "writable" replaces true
                "define": "readonly",
                "hqDefine": "readonly",
                "hqImport": "readonly",
                "hqRequire": "readonly",
                "requirejs": "readonly",
                "gettext": "readonly",
                "ngettext": "readonly",
                "interpolate": "readonly",
                "assert": "readonly",
                "sinon": "readonly",
                "$": "readonly",
                "ko": "readonly",
                "_": "readonly",
                "L": "writable",
                "it": "readonly",
                "describe": "readonly",
                "beforeEach": "readonly",
                "afterEach": "readonly",
                "nv": "readonly",
                "d3": "readonly",
            },
        },

        // http://eslint.org/docs/rules/
        // http://eslint.org/docs/latest/use/configure/rules
        rules: {
            // First option can be off, warn, or error
            "brace-style": ["error", "1tbs", { "allowSingleLine": true }],
            "camelcase": ["error", {"properties": "never"}],
            "comma-dangle": ["warn", "always-multiline"],
            "curly": ["error"],
            "eqeqeq": ["error"],
            "func-call-spacing": ["error"],
            "indent": ["warn", 4, {"SwitchCase": 1, "FunctionDeclaration": {"parameters": "first"}}],
            "linebreak-style": ["error", "unix"],
            "key-spacing": ["error"],
            "keyword-spacing": ["error"],
            "no-implicit-globals": ["error"],
            "no-irregular-whitespace": ["error"],
            "no-new-object": ["error"],
            "no-regex-spaces": ["error"],
            "no-throw-literal": ["error"],
            "no-unneeded-ternary": ["error"],
            "no-unused-vars": ["error", {argsIgnorePattern: "^_", varsIgnorePattern: "^_"}],
            "no-whitespace-before-property": ["error"], // match ruff E201 and E211
            "one-var-declaration-per-line": ["error"],
            "semi": ["error", "always"],
            "space-before-function-paren": ["error", {"anonymous": "always", "named": "never", "asyncArrow": "always"}],
            "space-before-blocks": ["error"],
            "space-in-parens": ["error", "never"],
            "space-infix-ops": ["error"],   // match ruff E225
            "strict": ["warn", "global"],
        },
    },
];
