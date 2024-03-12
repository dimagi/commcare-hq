$(function () {
    'use strict';
    let initialPageData = hqImport("hqwebapp/js/initial_page_data");
    ace.config.set('basePath', initialPageData.get('ace_base_path'));
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
    _.each(["h2", "h3", "h4"], function (header) {
        $(header).each(function () {
            let headerId = $(this).attr('id');
            if (headerId === undefined) return;

            let $copyLinkToSection = $('<a href="#' + headerId + '" class="d-inline-block" />').append($('<i class="fa fa-link"></i>'));
            $(this).addClass('d-inline-block pe-3').after(
                $copyLinkToSection
            );
            new bootstrap.Tooltip($copyLinkToSection.get(0), {
                title: "Click to copy link to section.",
                placement: "right",
            });
            $copyLinkToSection.click(function (e) {
                e.preventDefault();
                let fullLink = window.location.origin + window.location.pathname + $(this).attr('href');
                navigator.clipboard.writeText(fullLink);
                $(this).blur();
            });
        });
    });
});
