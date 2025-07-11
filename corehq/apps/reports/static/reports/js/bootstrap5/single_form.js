/*
    Interactivity for a single form. Used on the list of forms in the Case History tab when viewing a case, and
    also in the single form view page that's accessible from the submission history report or the "View standalone
    form" button when looking at a form in case history.
*/
import $ from "jquery";
import _ from "underscore";
import assertProperties from "hqwebapp/js/assert_properties";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap5/main";
import googleAnalytics from "analytix/js/google";
import noopMetrics from "analytix/js/noopMetrics";
import readableForm from "reports/js/bootstrap5/readable_form";
import dataCorrections from "reports/js/bootstrap5/data_corrections";
import Clipboard from "clipboard/dist/clipboard";

var initSingleForm = function (options) {
    assertProperties.assert(options, ['instance_id', 'form_question_map', 'ordered_question_values'], ['container']);

    var $container = options.container || $("body");

    var analyticsUsage = function (action, callback) {
        var label = 'standalone_form',
            extra = {},
            caseId = initialPageData.get("context_case_id");
        if (caseId) {
            label = 'case';
        }
        googleAnalytics.track.event('Edit Data', action, label, '', extra, callback);
    };

    $('.hq-help-template', $container).each(function () {
        hqMain.transformHelpTemplate($(this), true);
    });

    $('#edit-form', $container).click(function () {
        analyticsUsage('Edit Form Submission');
        noopMetrics.track.event("Clicked Edit Form Submission");
    });

    readableForm.init();

    dataCorrections.init($container.find(".data-corrections-trigger"), $container.find(".data-corrections-modal"), {
        properties: options.form_question_map,
        propertyNames: options.ordered_question_values,
        propertyPrefix: "<div class='form-data-question'><i data-bind='attr: { class: icon }'></i> ",
        propertySuffix: "</div>",
        displayProperties: [
            {
                property: 'label',
                name: gettext('Labels'),
            },
            {
                property: 'name',
                name: gettext('Question IDs'),
            },
        ],
        saveUrl: initialPageData.reverse("edit_form", options.instance_id),
        analyticsDescriptor: 'Clean Form Data',
    });

    $("#archive-form", $container).submit(function () {
        document.getElementById('archive-form-btn').disabled = true;
        $('#archive-spinner', $container).show();

        // _.after(2,...) means the callback will only be called after *both* analytics
        // functions have finished.
        var analyticsCallback = _.after(2, function () {
            document.getElementById('archive-form').submit();
        });
        analyticsUsage('Archive Form Submission', analyticsCallback);
        noopMetrics.track.event("Clicked on Archive Form", {}, analyticsCallback);

        return false;
    });
    $("#unarchive-form", $container).submit(function () {
        document.getElementById('unarchive-form-btn').disabled = true;
        $('#unarchive-spinner', $container).show();
        googleAnalytics.track.event('Reports', 'Case History', 'Restore this form', "", {}, function () {
            document.getElementById('unarchive-form').submit();
        });
        return false;
    });
    $("#resave-form", $container).submit(function () {
        document.getElementById('resave-form-btn').disabled = true;
        $('#resave-spinner', $container).show();
    });

    var clipboard = new Clipboard('.copy-xml', { text: function () { return $('#form-xml pre', $container).text(); } }),
        $copyBtn = $('.copy-xml', $container);
    $copyBtn.tooltip({  /* todo B5: plugin:tooltip */
        title: gettext("Copied!"),
    });
    clipboard.on('success', function () {
        $copyBtn.tooltip('show');  /* todo B5: plugin:tooltip */
        window.setTimeout(function () { $copyBtn.tooltip('hide'); }, 1000);  /* todo B5: plugin:tooltip */
    });
};

export default {
    initSingleForm: initSingleForm,
};
