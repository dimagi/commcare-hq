hqDefine('hqwebapp/js/base_ace', [
    'jquery',
    'ace-builds/src-min-noconflict/ace',
], function (
    $,
    ace
) {

    function initAceEditor(element, mode, options, value) {

        hqRequire(['ace-builds/src-min-noconflict/mode-json',
            'ace-builds/src-min-noconflict/mode-xml'], function () {

            var defaultOptions = {
                showPrintMargin: false,
                maxLines: 40,
                minLines: 3,
                fontSize: 14,
                wrap: true,
                useWorker: true,
            };
            options = $.extend(defaultOptions, options);

            var editor = ace.edit(element, options);

            editor.session.setMode(mode);
            if (value) {
                editor.getSession().setValue(value);
            }

        });

    }

    return {
        initAceEditor: initAceEditor,
    };
});
