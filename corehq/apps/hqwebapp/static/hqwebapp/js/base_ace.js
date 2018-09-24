hqDefine('hqwebapp/js/base_ace', [
    'jquery',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
], function (
    $,
    ace
) {

    var initAceEditor = function (element, mode, options, value) {
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
        return editor;

    };


    var initJsonWidget = function (element) {
        var $element = $(element),
            editorElement = $element.after('<pre />').next()[0];
        var editor = initAceEditor(editorElement, 'ace/mode/json', {}, $element.val());
        $element.hide();

        editor.getSession().on('change', function () {
            $element.val(editor.getSession().getValue());
        });
    };


    $(function () {
        _.each($('.jsonwidget'), initJsonWidget);
    });

    return {
        initJsonWidget: initJsonWidget,
        initAceEditor: initAceEditor,
    };
});
