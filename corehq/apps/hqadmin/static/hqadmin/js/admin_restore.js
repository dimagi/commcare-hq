/* globals hqDefine ace */
hqDefine('hqadmin/js/admin_restore',[
    "jquery",
    "ace-builds/src-min-noconflict/ace",
    "jquery-treetable/jquery.treetable",
],function ($,ace) {
    $(function() {
        $("#timingTable").treetable();
        var element = document.getElementById("payload");
        var editor = ace.edit(
            element,
            {
                showPrintMargin: false,
                maxLines: 40,
                minLines: 3,
                fontSize: 14,
                wrap: true,
                useWorker: false, // enable the worker to show syntax errors
            }
        );
        editor.session.setMode('ace/mode/xml');
        editor.setReadOnly(true);
        editor.session.setValue($("#payload").data('payload'));
    });
});
