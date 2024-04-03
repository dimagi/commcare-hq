/*
    Interactivity for a single form. Used on the list of forms in the Case History tab when viewing a case, and
    also in the single form view page that's accessible from the submit history report or the "View standalone
    form" button when looking at a form in case history.
*/
hqDefine("reports/js/bootstrap5/single_form", [
    "jquery",
    "underscore",
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap5/main",
    "analytix/js/google",
    "analytix/js/kissmetrix",
    "reports/js/readable_form",
    "reports/js/data_corrections",
    "clipboard/dist/clipboard",
], function (
    $,
    _,
    assertProperties,
    initialPageData,
    hqMain,
    googleAnalytics,
    kissAnalytics,
    readableForm,
    dataCorrections,
    Clipboard
) {
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
            kissAnalytics.track.event("Clicked Edit Form Submission");
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
            kissAnalytics.track.event("Clicked on Archive Form", {}, analyticsCallback);

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
        $copyBtn.tooltip({
            title: gettext("Copied!"),
        });
        clipboard.on('success', function () {
            $copyBtn.tooltip('show');
            window.setTimeout(function () { $copyBtn.tooltip('hide'); }, 1000);
        });
    };

    return {
        initSingleForm: initSingleForm,
    };
});
