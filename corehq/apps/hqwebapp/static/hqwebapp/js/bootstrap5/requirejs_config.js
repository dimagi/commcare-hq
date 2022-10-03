requirejs.config({
    baseUrl: '/static/',
    paths: {
        "babel": "@babel/standalone/babel.min",
        "babel-plugin-transform-modules-requirejs-babel": "babel-plugin-transform-modules-requirejs-babel/index",
        "backbone": "backbone/backbone-min",
        "backbone.radio": "backbone.radio/build/backbone.radio.min",
        "backbone.marionette": "backbone.marionette/lib/backbone.marionette.min",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "bootstrap5": "bootstrap5/dist/js/bootstrap.bundle.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.bootstrap": "datatables.net-bs5/js/dataTables.bootstrap5.min",
        "datatables.fixedColumns": "datatables.net-fixedcolumns/js/dataTables.fixedColumns.min",
        "datatables.fixedColumns.bootstrap": "datatables.net-fixedcolumns/js/dataTables.fixedColumns.min",
        "datetimepicker": "@eonasdan/tempus-dominus/dist/js/jQuery-provider.min",  // import this if you need jquery plugin of tempus-dominus
        "es6": "requirejs-babel7/es6",
        "jquery": "jquery/dist/jquery.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "popper": "@popperjs/core/dist/umd/popper.min",
        "sentry_browser": "sentry/js/sentry.browser.7.28.0.min",
        "sentry_captureconsole": "sentry/js/sentry.captureconsole.7.28.0.min",
        "tempus-dominus": "eonasdan/tempus-dominus/dist/js/tempus-dominus.min",
        "underscore": "underscore/underscore",
    },
    shim: {
        "accounting/js/lib/stripe": { exports: 'Stripe' },
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "ace-builds/src-min-noconflict/mode-json": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "ace-builds/src-min-noconflict/mode-xml": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "ace-builds/src-min-noconflict/ext-searchbox": { deps: ["ace-builds/src-min-noconflict/ace"] },
        "At.js/dist/js/jquery.atwho": { deps: ['jquery', 'Caret.js/dist/jquery.caret'] },
        "backbone": { exports: "backbone" },
        "datatables.bootstrap": { deps: ['datatables'] },
        "datatables.fixedColumns.bootstrap": { deps: ['datatables.fixedColumns'] },
        "datetimepicker": {
            deps: ['popper', 'tempus-dominus'],
        },
        "d3/d3.min": {
            "exports": "d3",
        },
        "hqwebapp/js/bootstrap5/hq.helpers": { deps: ['jquery', 'knockout', 'underscore'] },
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

    // This is really build config, but it's easier to define a js function here than in bootstrap5/requirejs.yml
    // The purpose of this is to replace hqDefine and hqRequire calls, which in a requirejs context are
    // just pass throughs to define and require, with actual calls to define and require. This is needed
    // because r.js's dependency tracing depends on parsing define and require calls.
    onBuildRead: function (moduleName, path, contents) {
        return contents.replace(/\bhqDefine\b/g, 'define').replace(/\bhqRequire\b/g, 'require');
    },
});
