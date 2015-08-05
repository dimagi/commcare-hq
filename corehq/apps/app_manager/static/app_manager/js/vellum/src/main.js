
require.config({
    paths: {
        vellum: "."
    },
    bundles: {
        "global-deps": [
            "jquery", 
            "jquery.bootstrap"
        ], 
        "local-deps": [
            "underscore", 
            "jquery.jstree", 
            "jquery.bootstrap-popout", 
            "save-button", 
            "css/css!../lib/codemirror/codemirror", 
            "css/css!../bower_components/jstree/dist/themes/default/style", 
            "css/css!yui-combo", 
            "css/css!../bower_components/At.js/dist/css/jquery.atwho"
        ], 
        "main-components": [
            "vellum/core", 
            "vellum/ignoreButRetain", 
            "vellum/intentManager", 
            "vellum/itemset", 
            "vellum/javaRosa", 
            "vellum/datasources", 
            "vellum/lock", 
            "vellum/databrowser", 
            "vellum/commtrack", 
            "vellum/modeliteration", 
            "vellum/saveToCase", 
            "vellum/uploader", 
            "vellum/window", 
            "vellum/polyfills", 
            "vellum/copy-paste"
        ]
    }
});

// stubs (stubModules build option puts them in exclude.js, which is removed)
define('css/css', {});
define('less/less', {});

define([
    'jquery',
    'vellum/core',
    'vellum/ignoreButRetain',
    'vellum/intentManager',
    'vellum/itemset',
    'vellum/javaRosa',
    'vellum/datasources',
    'vellum/lock',
    'vellum/databrowser',
    'vellum/commtrack',
    'vellum/modeliteration',
    'vellum/saveToCase',
    'vellum/uploader',
    'vellum/window',
    'vellum/polyfills',
    'vellum/copy-paste'
], function () {});

