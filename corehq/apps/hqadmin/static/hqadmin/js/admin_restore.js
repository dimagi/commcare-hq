/* globals hqDefine ace */
hqDefine('hqadmin/js/admin_restore',[
    "jquery",
    "hqwebapp/js/base_ace",
    "jquery-treetable/jquery.treetable",
],function ($, baseAce) {
    $(function () {
        $("#timingTable").treetable();
        var element = document.getElementById("payload");

        baseAce.initAceEditor(element, 'ace/mode/xml', {
            showPrintMargin: false,
            useWorker: false,
            readOnly: true,
        }, $("#payload").data('payload'));


    });
});
