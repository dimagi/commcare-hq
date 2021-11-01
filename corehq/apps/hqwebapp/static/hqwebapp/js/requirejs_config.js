/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        "datatables.scroller": "datatables-scroller/js/dataTables.scroller",
        "datatables.colReorder": "datatables-colreorder/js/dataTables.colReorder",
        "d3/d3.min": "d3/dist/d3.min",
        "d3-graphviz": "d3-graphviz/build/d3-graphviz.min",
        "d3-dispatch": "d3-dispatch/dist/d3-dispatch.min",
        "d3-transition": "d3-transition/dist/d3-transition.min",
        "d3-selection": "d3-selection/dist/d3-selection.min",
        "d3-timer": "d3-timer/dist/d3-timer.min",
        "d3-interpolate": "d3-interpolate/dist/d3-interpolate.min",
        "d3-zoom": "d3-zoom/dist/d3-zoom.min",
        "d3-format": "d3-format/dist/d3-format.min",
        "d3-path": "d3-path/dist/d3-path.min",
        "d3-color": "d3-color/dist/d3-color.min",
        "d3-drag": "d3-drag/dist/d3-drag.min",
        "d3-ease": "d3-ease/dist/d3-ease.min",
        "@hpcc-js/wasm": "@hpcc-js/wasm/dist/index.min",
    },
    shim: {
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "bootstrap": { deps: ['jquery'] },
        "ko.mapping": { deps: ['knockout'] },
        "hqwebapp/js/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
        "datatables.bootstrap": { deps: ['datatables'] },
        "jquery.rmi/jquery.rmi": {
            deps: ['jquery', 'knockout', 'underscore'],
            exports: 'RMI',
        },
        "accounting/js/lib/stripe": { exports: 'Stripe' },
        "d3/d3.min": {
            exports: "d3",
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
        "datatables.scroller": {
            "datatables.net": "datatables",
        },
        "datatables.colReorder": {
            "datatables.net": "datatables",
        },
    },

    // This is really build config, but it's easier to define a js function here than in requirejs.yaml
    // The purpose of this is to replace hqDefine and hqRequire calls, which in a requirejs context are
    // just pass throughs to define and require, with actual calls to define and require. This is needed
    // because r.js's dependency tracing depends on parsing define and require calls.
    onBuildRead: function (moduleName, path, contents) {
        return contents.replace(/\bhqDefine\b/g, 'define').replace(/\bhqRequire\b/g, 'require');
    },
});
