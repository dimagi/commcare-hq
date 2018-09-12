
hqDefine('app_manager/js/download_index_main',[
    'jquery',
    'underscore',
    'ace-builds/src-min-noconflict/ace',
    'app_manager/js/download_async_modal',
    'app_manager/js/source_files',
    'd3/d3.min'
],function () {

    hqRequire(['ace-builds/src-min-noconflict/mode-json'],function () {
        alert("heheheheeheh");
    }) ;
    // ace.config.set('basePath', '/ace-builds/src-noconflict');
    // $(function () {
    //     var elements = $('.prettyprint');
    //
    //     _.each(elements, function (elem) {
    //         var editor = ace.edit(
    //             elem,
    //             {
    //                 showPrintMargin: false,
    //                 maxLines: 40,
    //                 minLines: 3,
    //                 fontSize: 14,
    //                 wrap: true,
    //                 useWorker: false, // enable the worker to show syntax errors
    //             }
    //         );
    //         var fileName = $(elem).data('filename');
    //
    //         if (fileName.endsWith('json')) {
    //             editor.session.setMode('ace/mode/json');
    //         } else {
    //             editor.session.setMode('ace/mode/xml');
    //         }
    //         editor.setReadOnly(true);
    //     });
    //
    // });
});