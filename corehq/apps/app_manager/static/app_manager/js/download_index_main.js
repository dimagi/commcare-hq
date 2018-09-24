hqDefine('app_manager/js/download_index_main',[
    'jquery',
    'underscore',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json', //to the ace mode from CDN
    'ace-builds/src-min-noconflict/mode-xml',
    'app_manager/js/download_async_modal',
    'app_manager/js/source_files',
],function ($, _, ace) {

    $(function () {

        var elements = $('.prettyprint');
        _.each(elements, function (elem) {

            var editor = ace.edit(
                elem,
                {
                    showPrintMargin: false,
                    maxLines: 40,
                    minLines: 3,
                    fontSize: 14,
                    wrap: true,
                    useWorker: false,
                }
            );

            var fileName = $(elem).data('filename');
            if (fileName.endsWith('json')) {
                editor.session.setMode('ace/mode/json');
            } else {
                editor.session.setMode('ace/mode/xml');
            }
            editor.setReadOnly(true);
        });


    });

});