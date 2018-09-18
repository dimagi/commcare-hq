hqDefine('userreports/js/base', [
    'jquery',
    'ace-builds/src-min-noconflict/ace',
], function (
    $,
    ace
) {
    function initJsonWidget(element) {
        var $element = $(element),
            editorElement = $element.after('<pre />').next()[0];
        $element.hide();
        var editor = ace.edit(
            editorElement,
            {
                showPrintMargin: false,
                maxLines: 40,
                minLines: 3,
                fontSize: 14,
                wrap: true,
                useWorker: true,
            }
        );
        editor.session.setMode('ace/mode/json');
        editor.getSession().setValue($element.val());
        editor.getSession().on('change', function () {
            $element.val(editor.getSession().getValue());
        });
    }

    $(function () {
        _.each($('.jsonwidget'), initJsonWidget);
    });

    return {
        initJsonWidget: initJsonWidget,
    };
});
