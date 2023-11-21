/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "ckeditor5": "ckeditor5/build/ckeditor5-dll",
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables-fixedcolumns/js/dataTables.fixedColumns",
        "datatables.bootstrap": "datatables-bootstrap3/BS3/assets/js/datatables",
    },
    shim: {
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "bootstrap": { deps: ['jquery'] },
        "ckeditor5": { exports: "CKEditor5" },
        "@ckeditor/ckeditor5-editor-classic/build/editor-classic": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-autoformat/build/autoformat": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-basic-styles/build/basic-styles": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-block-quote/build/block-quote": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-essentials/build/essentials": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-font/build/font": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-heading/build/heading": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-horizontal-line/build/horizontal-line": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-html-support/build/html-support": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-restricted-editing/build/restricted-editing": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-image/build/image": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-indent/build/indent": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-link/build/link": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-list/build/list": { deps: ["ckeditor5"] },
        "@ckeditor/ckeditor5-paste-from-office/build/paste-from-office": { deps: ["ckeditor5"] },
        "ko.mapping": { deps: ['knockout'] },
        "hqwebapp/js/bootstrap3/hq.helpers": { deps: ['jquery', 'bootstrap', 'knockout', 'underscore'] },
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
