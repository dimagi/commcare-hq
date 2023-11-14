$(function () {
    'use strict';
    _.each(["python", "html", "js"], function (lang) {
        $('pre[data-lang="' + lang + '"]').each(function () {
            let editor = ace.edit($(this).get(0), {
                    showPrintMargin: false,
                    maxLines: 20,
                    minLines: 1,
                    fontSize: 13,
                    wrap: true,
                    useWorker: false,
                    showGutter: false,
                    theme: "ace/theme/chrome",
                    highlightActiveLine: false,
                }),
                aceLang = (lang === "js") ? "javascript" : lang;
            editor.setReadOnly(true);
            editor.session.setMode('ace/mode/' + aceLang);
        });
    });
});
