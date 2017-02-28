/* globals hqDefine */
hqDefine('hqadmin/js/admin_restore.js', function () {
    $(function() {
        var payloadElement = document.getElementById('payload');
        var myCodeMirror = CodeMirror(function(elt) {
            payloadElement.parentNode.replaceChild(elt, payloadElement);
        }, {
            value: payloadElement.textContent,
            readOnly: true,
            lineNumbers: true,
            mode: {name: "text/xml", json: true},
            viewportMargin: Infinity,
            foldGutter: true,
            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"]
        });

        $("#timingTable").treetable();
    });
});
