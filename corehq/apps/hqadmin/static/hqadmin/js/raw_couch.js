/* globals hqDefine */
hqDefine('hqadmin/js/raw_couch', function () {
    $(function() {
        // don't break if offline (Also why I left it as a <pre/>)
        if (window.CodeMirror) {
            var couchDocElement = document.getElementById('couch-document');
            if (couchDocElement) {
                var myCodeMirror = CodeMirror(function(elt) {
                    couchDocElement.parentNode.replaceChild(elt, couchDocElement);
                }, {
                    value: couchDocElement.textContent,
                    readOnly: true,
                    lineNumbers: true,
                    mode: {name: "javascript", json: true},
                    viewportMargin: Infinity,
                    foldGutter: true,
                    gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
                });
            }
        }
    });
});
