/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "es6": "requirejs-babel7/es6",
        "babel": "@babel/standalone/babel.min",
        "babel-plugin-transform-modules-requirejs-babel": "babel-plugin-transform-modules-requirejs-babel/index",
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "backbone": "backbone/backbone-min",
        "backbone.radio": "backbone.radio/build/backbone.radio.min",
        "backbone.marionette": "backbone.marionette/lib/backbone.marionette.min",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        "sentry_browser": "sentry/js/sentry.browser.7.28.0.min",
        "sentry_captureconsole": "sentry/js/sentry.captureconsole.7.28.0.min",
    },
    shim: {
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "ace-builds/src-min-noconflict/mode-json": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "ace-builds/src-min-noconflict/mode-xml": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "ace-builds/src-min-noconflict/ext-searchbox": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "At.js/dist/js/jquery.atwho": { deps: ['jquery', 'Caret.js/dist/jquery.caret'] },
        "backbone": { exports: "backbone" },
        "bootstrap": { deps: ['jquery'] },
        "calendars/dist/js/jquery.calendars.picker": {
            deps: [
                "calendars/dist/js/jquery.plugin",
                "calendars/dist/js/jquery.calendars",
            ],
        },
        "calendars/dist/js/jquery.calendars.ethiopian": {
            deps: [
                "calendars/dist/js/jquery.calendars",
            ],
        },
        "calendars/dist/js/jquery.calendars.plus": {
            deps: [
                "calendars/dist/js/jquery.calendars",
            ],
        },
        "calendars/dist/js/jquery.calendars-am": {
            deps: [
                "calendars/dist/js/jquery.calendars.picker",
                "calendars/dist/js/jquery.calendars",
            ],
        },
        "calendars/dist/js/jquery.calendars.picker-am": {
            deps: [
                "calendars/dist/js/jquery.calendars.picker",
                "calendars/dist/js/jquery.calendars",
            ],
        },
        "calendars/dist/js/jquery.calendars.ethiopian-am": {
            deps: [
                "calendars/dist/js/jquery.calendars.picker",
                "calendars/dist/js/jquery.calendars.ethiopian",
            ],
        },
        "ko.mapping": { deps: ['knockout'] },
        "hqwebapp/js/bootstrap3/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
        "sentry_browser": { exports: "Sentry" },
        "datatables.bootstrap": { deps: ['datatables'] },
        "jquery.rmi/jquery.rmi": {
            deps: ['jquery', 'knockout', 'underscore'],
            exports: 'RMI',
        },
        "accounting/js/lib/stripe": { exports: 'Stripe' },
        "d3/d3.min": {
            "exports": "d3",
        },
        "nvd3/nv.d3.min": {
            deps: ['d3/d3.min'],
            exports: 'nv',
        },
        "hqwebapp/js/lib/modernizr": {
            exports: 'Modernizr',
        },
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
