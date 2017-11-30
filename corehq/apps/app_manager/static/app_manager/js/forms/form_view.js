/* globals analytics, hqImport, SyntaxHighlighter, Util, django */
hqDefine("app_manager/js/forms/form_view", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
    hqImport('app_manager/js/app_manager').setAppendedPageTitle(django.gettext("Form Settings"));

    function formFilterMatches(filter, pattern_matches, substring_matches) {
        if (typeof(filter) !== 'string') {
            return false;
        }

        var result = false;
        $.each(pattern_matches, function(index, pattern) {
            result = result || filter.match(pattern);
        });

        $.each(substring_matches, function(index, sub) {
            result = result || filter.indexOf(sub) !== -1;
        });

        return result;
    }

    function FormFilter() {
        var self = this;
        var patterns = initial_page_data('form_filter_patterns');

        self.formFilter = ko.observable(initial_page_data('form_filter'));

        self.caseReferenceNotAllowed = ko.computed(function() {
            var moduleUsesCase = initial_page_data('all_other_forms_require_a_case') && initial_page_data('form_requires') === 'case';
            if (!moduleUsesCase || (initial_page_data('put_in_root') && !initial_page_data('root_requires_same_case'))) {
                // We want to determine here if the filter expression references
                // any case but the user case.
                var filter = self.formFilter();
                if (typeof(filter) !== 'string') {
                    return true;
                }

                $.each(patterns.usercase_substring, function(index, sub) {
                    filter = filter.replace(sub, '');
                });

                if (formFilterMatches(filter, patterns.case, patterns.case_substring)) {
                    return true;
                }
            }
            return false;
        });

        self.userCaseReferenceNotAllowed = ko.computed(function() {
            return !initial_page_data('is_usercase_in_use') && formFilterMatches(
                self.formFilter(), patterns.usercase, patterns.usercase_substring
            );
        });

        self.allowed = ko.computed(function () {
            return !self.formFilter() || !self.caseReferenceNotAllowed() && !self.userCaseReferenceNotAllowed();
        });
    }

    $(function (){
        // Validation for build
        var setupValidation = hqImport('app_manager/js/app_manager').setupValidation;
        setupValidation(hqImport("hqwebapp/js/initial_page_data").reverse("validate_form_for_build"));

        // Analytics for renaming form
        $(".appmanager-edit-title").on('click', '.btn-success', function() {
            hqImport('analytix/js/kissmetrix').track.event("Renamed form from form settings page");
        });

        // Settings > Logic
        var $formFilter = $('#form-filter');
        if ($formFilter.length && initial_page_data('allow_form_filtering')) {
            $('#form-filter').koApplyBindings(new FormFilter());
        }

        if (initial_page_data('allow_form_workflow')) {
            var FormWorkflow = hqImport('app_manager/js/forms/form_workflow').FormWorkflow;
            var labels = {};
            labels[FormWorkflow.Values.DEFAULT] = gettext("Home Screen");
            labels[FormWorkflow.Values.ROOT] = gettext("First Menu");
            labels[FormWorkflow.Values.MODULE] = gettext("Menu: ") + initial_page_data('module_name');
            if (initial_page_data('root_module_name')) {
                labels[FormWorkflow.Values.PARENT_MODULE] = gettext("Parent Menu: ") + initial_page_data('root_module_name');
            }
            labels[FormWorkflow.Values.PREVIOUS_SCREEN] = gettext("Previous Screen");

            var options = {
                labels: labels,
                workflow: initial_page_data('post_form_workflow'),
                workflow_fallback: initial_page_data('post_form_workflow_fallback'),
            };

            if (hqImport('hqwebapp/js/toggles').toggleEnabled('FORM_LINK_WORKFLOW') || initial_page_data('uses_form_workflow')) {
                labels[FormWorkflow.Values.FORM] = gettext("Link to other form");
                options.forms = initial_page_data('linkable_forms');
                options.formLinks = initial_page_data('form_links');
                options.formDatumsUrl = hqImport('hqwebapp/js/initial_page_data').reverse('get_form_datums');
            }

            $('#form-workflow').koApplyBindings(new FormWorkflow(options));
        }

        // Settings > Advanced
        $('#auto-gps-capture').koApplyBindings({
            auto_gps_capture: ko.observable(initial_page_data('auto_gps_capture')),
        });

        var $shadowParent = $('#shadow-parent');
        if ($shadowParent.length) {
            $shadowParent.koApplyBindings({
                shadow_parent: ko.observable(initial_page_data('shadow_parent_form_id')),
            });
        } else if (hqImport('hqwebapp/js/toggles').toggleEnabled('NO_VELLUM')) {
            $('#no-vellum').koApplyBindings({
                no_vellum: ko.observable(initial_page_data('no_vellum')),
            });
        }

        if (hqImport('hqwebapp/js/toggles').toggleEnabled('CUSTOM_INSTANCES')) {
            var customInstances = hqImport('app_manager/js/forms/custom_instances').wrap({
                customInstances: initial_page_data('custom_instances'),
            });
            $('#custom-instances').koApplyBindings(customInstances);
        }

        // Case Management > Data dictionary descriptions for case properties
        $('.property-description').popover();

        // Advanced > XForm > Upload
        $("#xform_file_input").change(function(){
            if ($(this).val()) {
                $("#xform_file_submit").show();
            } else {
                $("#xform_file_submit").hide();
            }
        }).trigger('change');

        // Advanced > XForm > View
        $("#xform-source-opener").click(function(evt){
            if (evt.shiftKey) {
                // Shift+click: edit form source
                $(".source-readonly").hide();
                $(".source-edit").show();
                $.get($(this).data('href'), function (data) {
                    $("#xform-source-edit").text(data).blur();
                }, 'json');
            } else {
                // Plain click: view form source
                $(".source-edit").hide();
                $(".source-readonly").show();
                $("#xform-source").text("Loading...");
                $.get($(this).data('href'), function (data) {
                    var brush = new SyntaxHighlighter.brushes.Xml();
                    brush.init({ toolbar: false });
                    // brush.getDiv seems to escape inconsistently, so I'm helping it out
                    data = data.replace(/&/g, '&amp;');
                    $("#xform-source").html(brush.getDiv(data));
                }, 'json');
            }
            $(".xml-source").modal();
        });
    });
});
