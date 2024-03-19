"use strict";
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "babel": "@babel/standalone/babel.min",
        "babel-plugin-transform-modules-requirejs-babel": "babel-plugin-transform-modules-requirejs-babel/index",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "es6": "requirejs-babel7/es6",
        "jquery": "jquery/dist/jquery.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "sentry_browser": "sentry/js/sentry.browser.7.28.0.min",
        "sentry_captureconsole": "sentry/js/sentry.captureconsole.7.28.0.min",
        "underscore": "underscore/underscore",
    },
    shim: {
        "accounting/js/lib/stripe": { exports: 'Stripe' },
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "bootstrap": { deps: ['jquery'] },
        "datatables.bootstrap": { deps: ['datatables'] },
        "d3/d3.min": {
            "exports": "d3",
        },
        "hqwebapp/js/bootstrap3/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
        "hqwebapp/js/lib/modernizr": {
            exports: 'Modernizr',
        },
        "jquery.rmi/jquery.rmi": {
            deps: ['jquery', 'knockout', 'underscore'],
            exports: 'RMI',
        },
        "ko.mapping": { deps: ['knockout'] },
        "nvd3/nv.d3.min": {
            deps: ['d3/d3.min'],
            exports: 'nv',
        },
        "sentry_browser": { exports: "Sentry" },
    },
    packages: [{
        name: 'moment',
        location: 'moment',
        main: 'moment',
    }],
    map: {
        "datatables.fixedColumns": {
            "datatables.net": "datatables",
        },
    },

    // This is really build config, but it's easier to define a js function here than in bootstrap3/requirejs.yml
    // The purpose of this is to replace hqDefine and hqRequire calls, which in a requirejs context are
    // just pass throughs to define and require, with actual calls to define and require. This is needed
    // because r.js's dependency tracing depends on parsing define and require calls.
    onBuildRead: function (moduleName, path, contents) {
        return contents.replace(/\bhqDefine\b/g, 'define').replace(/\bhqRequire\b/g, 'require');
    },
});
