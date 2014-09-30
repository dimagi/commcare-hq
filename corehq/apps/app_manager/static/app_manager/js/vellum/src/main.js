
require.config({
    paths: {
        vellum: "."
    },
    bundles: {
        "global-deps": [
            "jquery", 
            "jquery-ui", 
            "jquery.bootstrap", 
            "css/css!../lib/jquery-ui/redmond/jquery-ui-1.8.14.custom"
        ], 
        "local-deps": [
            "underscore", 
            "jquery.jstree", 
            "jquery.fancybox", 
            "jquery.bootstrap-popout", 
            "jquery.bootstrap-better-typeahead", 
            "save-button", 
            "css/css!../lib/codemirror/codemirror", 
            "css/css!../lib/jstree/default/style", 
            "css/css!../lib/fancybox/jquery.fancybox-1.3.4", 
            "css/css!yui-combo"
        ], 
        "main-components": [
            "vellum/core", 
            "vellum/ignoreButRetain", 
            "vellum/intentManager", 
            "vellum/itemset", 
            "vellum/javaRosa", 
            "vellum/lock", 
            "vellum/uploader", 
            "vellum/window", 
            "vellum/polyfills"
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
    'vellum/lock',
    'vellum/uploader',
    'vellum/window',
    'vellum/polyfills'
], function () {});

