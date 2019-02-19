hqDefine('hqwebapp/js/base_ace', [
    'jquery',
    'ace-builds/src-min-noconflict/ace',
], function (
    $,
    ace
) {

    if (!ace.config.get('basePath')) {
        var basePath = requirejs.s.contexts._.config.paths["ace-builds/src-min-noconflict/ace"];
        ace.config.set("basePath",basePath.substring(0,basePath.lastIndexOf("/")));
    }
    var initAceEditor = function (element, mode, options, value) {
        var defaultOptions = {
            showPrintMargin: false,
            maxLines: 40,
            minLines: 3,
            fontSize: 14,
            wrap: true,
            useWorker: false,
            readOnly: true,
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
        var editor = initAceEditor(editorElement, 'ace/mode/json', {
            useWorker: true,
            readOnly: false,
        }, $element.val());
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
