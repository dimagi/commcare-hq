/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "knockout": "knockout/dist/knockout.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "datatables": "datatables/media/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        "datatables.scroller": "datatables-scroller/js/dataTables.scroller",
        "datatables.colReorder": "datatables-colreorder/js/dataTables.colReorder",
    },
    shim: {
        "bootstrap": { deps: ['jquery'] },
        "ko.mapping": { deps: ['knockout'] },
        "hqwebapp/js/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
        "datatables.bootstrap": { deps: ['datatables'] },
        "jquery.rmi/jquery.rmi": {
            deps: ['jquery', 'knockout', 'underscore'],
            exports: 'RMI',
        },
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
    },
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
});
