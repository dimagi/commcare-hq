
requirejs.config({
    paths: {
        vellum: "."
    },
    bundles: {
        "global-deps": [
            "jquery",
            "jquery.bootstrap",
            "underscore"
        ],
        "local-deps": [
            "jquery.jstree",
            "jstree-actions",
            "save-button",
            "ckeditor",
            "ckeditor-jquery",
            "css/css!../node_modules/codemirror/lib/codemirror",
            "css/css!../node_modules/jstree/dist/themes/default/style",
            "css/css!yui-combo",
            "css/css!../node_modules/at.js/dist/css/jquery.atwho"
        ],
        "main-components": [
            "vellum/core",
            "vellum/ignoreButRetain",
            "vellum/intentManager",
            "vellum/itemset",
            "vellum/javaRosa/plugin",
            "vellum/datasources",
            "vellum/lock",
            "vellum/databrowser",
            "vellum/commtrack",
            "vellum/modeliteration",
            "vellum/saveToCase",
            "vellum/uploader",
            "vellum/window",
            "vellum/polyfills",
            "vellum/copy-paste",
            "vellum/commander",
            "vellum/commcareConnect"
        ]
    }
});

// stubs (stubModules build option puts them in exclude.js, which is removed)
define('css/css', {});
define('less/less', {});

if (!window.gettext) {
    window.gettext = function (arg) { return arg; };
    window.ngettext = function (singular, plural, count) {
        return count === 1 ? singular : plural;
    };
}

define([
    'jquery',
    'vellum/core',
    'vellum/ignoreButRetain',
    'vellum/intentManager',
    'vellum/itemset',
    'vellum/javaRosa/plugin',
    'vellum/datasources',
    'vellum/lock',
    'vellum/databrowser',
    'vellum/commtrack',
    'vellum/modeliteration',
    'vellum/saveToCase',
    'vellum/uploader',
    'vellum/window',
    'vellum/polyfills',
    'vellum/copy-paste',
    'vellum/commander',
    'vellum/commcareConnect'
], function () {});

