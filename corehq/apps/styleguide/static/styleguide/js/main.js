import 'commcarehq';
import $ from 'jquery';
import _ from 'underscore';
import 'htmx.org';

import ace from 'ace-builds/src-min-noconflict/ace';
import 'ace-builds/src-min-noconflict/mode-django';
import 'ace-builds/src-min-noconflict/mode-html';
import 'ace-builds/src-min-noconflict/mode-javascript';
import 'ace-builds/src-min-noconflict/mode-python';

import 'hqwebapp/js/bootstrap5/main';
import 'hqwebapp/js/bootstrap5/widgets';
import initialPageData from 'hqwebapp/js/initial_page_data';
import { Tooltip } from 'bootstrap5';

$(function () {
    ace.config.set('basePath', initialPageData.get('ace_base_path'));
    _.each(["python", "html", "js", "django"], function (lang) {
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
            if (headerId === undefined) {return;}

            let $copyLinkToSection = $('<a href="#' + headerId + '" class="d-inline-block" />').append($('<i class="fa fa-link"></i>'));
            $(this).addClass('d-inline-block pe-3').after(
                $copyLinkToSection,
            );
            new Tooltip($copyLinkToSection.get(0), {
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
