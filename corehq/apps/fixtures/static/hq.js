requirejs.config({
    baseUrl: '/static/',
    paths: {
        "jquery": "jquery/dist/jquery.min",
        "jquery.form": "jquery-form/jquery.form",
        "underscore": "underscore/underscore",
        "underscore-mixins": "style/js/underscore-mixins",
        "jquery.cookie": "jquery.cookie/jquery.cookie",
        "hq_extensions": "style/js/hq_extensions.jquery",
        "rmi": "jquery.rmi/jquery.rmi",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "django": "hqwebapp/js/django",
        "knockout": "knockout/dist/knockout.debug",
        "ko.mapping": "style/lib/knockout_plugins/knockout_mapping.ko.min",
        "ko.knockout_bindings": "style/ko/knockout_bindings.ko",
        "datatables": "datatables/media/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
        "select2": "select2-3.5.2-legacy/select2",
    },
    shim: {
        "bootstrap": { deps: ['jquery'] },
        "ko.mapping": { deps: ['knockout'] },
        "ko.knockout_bindings": { deps: ['knockout'] },
        "style/js/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
        "datatables.bootstrap": { deps: ['datatables'] },
    },
    map: {
        "datatables.fixedColumns": {
            "datatables.net": "datatables",
        },
    },
});
