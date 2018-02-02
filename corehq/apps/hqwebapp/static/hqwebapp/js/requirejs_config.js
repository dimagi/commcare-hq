/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "knockout": "knockout/dist/knockout.debug",
        "ko.mapping": "knockout-mapping/knockout.mapping",
        "datatables": "datatables/media/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
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
    },
    map: {
        "datatables.fixedColumns": {
            "datatables.net": "datatables",
        },
    },
});
