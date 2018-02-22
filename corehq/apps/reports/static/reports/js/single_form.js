/*
    Interactivity for a single form. Used on the list of forms in the Case History tab when viewing a case, and
    also in the single form view page that's accessible from the submit history report or the "View standalone
    form" button when looking at a form in case history.
*/
hqDefine("reports/js/single_form", function() {
    var initSingleForm = function($container) {
        $container = $container || $("body");

        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        var _analytics_usage = function(action, callback) {
            var label = 'standalone_form',
                extra = {},
                caseId = initial_page_data("context_case_id");
            if (caseId) {
                label = 'case';
            }
            hqImport('analytix/js/google').track.event('Edit Data', action, label, '', extra, callback);
        }

        $('.hq-help-template', $container).each(function () {
            hqImport("hqwebapp/js/main").transformHelpTemplate($(this), true);
        });

        // TODO: put this wherever
        $('#edit-form', $container).click(function() {
            _analytics_usage('Edit Form Submission')
        });

        // TODO: move to edit_properties_model.js? duplicated in case_details.js
        var $editPropertiesModal = $("#edit-dynamic-properties");
        if ($editPropertiesModal.length) {
            $("#edit-properties-trigger").click(function() {
                $editPropertiesModal.modal();
            });
            var properties = {};
            _.each(hqImport("hqwebapp/js/initial_page_data").get("form_data"), function(q) {
                properties[q.hashtagValue] = q.response;    // there's also q.label and q.value (which uses /data/)
            });
            $editPropertiesModal.koApplyBindings(new hqImport("reports/js/edit_properties_model").EditPropertiesModel({
                properties: properties,
            }));
        }

        $("#archive-form", $container).submit(function() {
            document.getElementById('archive-form-btn').disabled=true;
            $('#archive-spinner', $container).show();

            // _.after(2,...) means the callback will only be called after *both* analytics
            // functions have finished.
            var analyticsCallback = _.after(2, function() {
                    document.getElementById('archive-form').submit();
                }
            );
            _analytics_usage('Archive Form Submission', analyticsCallback);
            hqImport('analytix/js/kissmetrix').track.event("Clicked on Archive Form", {}, analyticsCallback);

            return false;
        });
        $("#unarchive-form", $container).submit(function() {
            document.getElementById('unarchive-form-btn').disabled=true;
            $('#unarchive-spinner', $container).show();
            hqImport('analytix/js/google').track.event('Reports', 'Case History', 'Restore this form', "", {}, function () {
                document.getElementById('unarchive-form').submit();
            });
            return false;
        });
        $("#resave-form", $container).submit(function() {
            document.getElementById('resave-form-btn').disabled=true;
            $('#resave-spinner', $container).show();
        });

        $.when(
            $.getScript(hqImport("hqwebapp/js/initial_page_data").get("clipboardScript"))
        ).done(function () {
            var clipboard = new Clipboard('.copy-xml', { text: function() { return $('#form-xml pre', $container).text(); } }),
                $copyBtn = $('.copy-xml', $container);
            $copyBtn.tooltip({
                title: gettext("Copied!"),
            });
            clipboard.on('success', function() {
                $copyBtn.tooltip('show');
                window.setTimeout(function() { $copyBtn.tooltip('hide'); }, 1000)
            });
        });
    };

    return {
        initSingleForm: initSingleForm,
    };
});
