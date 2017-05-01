/* globals CodeMirror */
hqDefine('userreports/js/base.js', function() {
    $(function () {
        if (!hqImport('hqwebapp/js/initial_page_data.js').get("code_mirror_off")) {
            $('.jsonwidget').each(function () {
                var elem = this;
                var codeMirror = CodeMirror.fromTextArea(elem, {
                    lineNumbers: true,
                    mode: {name: "javascript", json: true},
                    viewportMargin: Infinity,
                    foldGutter: true,
                    gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
                });
 
                var toggleLabel = $('label[for="' + this.id + '"]').click(function (e) {
                    $(codeMirror.display.wrapper).toggle();
                    setTimeout(adjustToggleAppearance, 0);
                    e.preventDefault();
                });
                var toggleIcon = $('<a href="#"></a>').prependTo(toggleLabel);
                function adjustToggleAppearance() {
                    if ($(codeMirror.display.wrapper).is(':hidden')) {
                        toggleIcon.html('<i class="icon-angle-right"></i>');
                    } else {
                        toggleIcon.html('<i class="icon-angle-down"></i>');
                    }
                }
                adjustToggleAppearance();
            });
        }
    });
});
