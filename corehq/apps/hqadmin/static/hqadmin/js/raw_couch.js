/* globals CodeMirror, hqDefine */
hqDefine('hqadmin/js/raw_couch', function () {
    $(function() {
        var $element = $("#couch-document");
        var editor = ace.edit(
            $element.get(0),
            {
                showPrintMargin: false,
                maxLines: 40,
                minLines: 3,
                fontSize: 14,
                wrap: true,
                useWorker: false,
            }
        );
        editor.session.setMode('ace/mode/json');
        editor.setReadOnly(true);
        editor.session.setValue(JSON.stringify($("#couch-document").data('doc'), null, 4));
    });
});
