hqDefine('hqadmin/js/admin_restore',[
    "jquery",
    "hqwebapp/js/base_ace",
    "jquery-treetable/jquery.treetable",
],function ($, baseAce) {
    $(function () {
        $("#timingTable").treetable();
        var element = document.getElementById("payload");

        baseAce.initAceEditor(element, 'ace/mode/xml', {}, $("#payload").data('payload'));


    });
});
