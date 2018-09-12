
hqDefine('app_manager/js/download_index_main',[
    'jquery',
    'underscore',
    'ace-builds/src-min-noconflict/ace',
    'app_manager/js/download_async_modal',
    'app_manager/js/source_files',
    'd3/d3.min'
],function ($, _, ace) {

    // var requirejsConfig = requirejs.s.contexts._.config;
    //
    // if(requirejsConfig.paths["ace-builds/src-min-noconflict/mode-json"])
    //     ace.config.setModuleUrl('ace/mode/json',requirejsConfig.paths["ace-builds/src-min-noconflict/mode-json"]);
    // if(requirejsConfig.paths["ace-builds/src-min-noconflict/mode-xml"])
    //     ace.config.setModuleUrl('ace/mode/xml',requirejsConfig.paths["ace-builds/src-min-noconflict/mode-xml"]);

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
                    useWorker: false, // enable the worker to show syntax errors
                }
            );
            var fileName = $(elem).data('filename');
            editor.setOption('useWorker',false);
            )
            if (fileName.endsWith('json')) {
                editor.session.setMode('ace/mode/json');
            } else {
                editor.session.setMode('ace/mode/xml');
            }
            editor.setReadOnly(true);
        });
    });

});