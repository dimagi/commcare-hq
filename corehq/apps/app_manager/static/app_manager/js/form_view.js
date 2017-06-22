/* globals analytics, COMMCAREHQ, SyntaxHighlighter, Util */
hqDefine("app_manager/js/form_view.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    hqImport('app_manager/js/app_manager.js').setAppendedPageTitle(django.gettext("Form Settings"));

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
            if (!moduleUsesCase || initial_page_data('put_in_root')) {
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
        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport("hqwebapp/js/urllib.js").reverse("validate_form_for_build"));

        // CloudCare "Preview Form" URL
        if (initial_page_data('allow_cloudcare') && !COMMCAREHQ.toggleEnabled('APP_MANAGER_V2')) {
            // tag the 'preview in cloudcare' button with the right url
            // unfortunately, has to be done in javascript
            var getCloudCareUrl = function(urlRoot, appId, moduleId, formId, caseId) {
                var url = urlRoot;
                if (appId !== undefined) {
                    url = url + "view/" + appId;
                    if (moduleId !== undefined) {
                        url = url + "/" + moduleId;
                        if (formId !== undefined) {
                            url = url + "/" + formId;
                            if (caseId !== undefined) {
                                url = url + "/" + caseId;
                            }
                        }
                    }
                }
                return url;
            };
            // build the previewCommand in the format that the CommCareSession will understand
            var getFormplayerUrl = function(urlRoot, appId, moduleId, formId) {
                var urlObject = new Util.CloudcareUrl({
                    'appId': appId,
                    'previewCommand': 'm' + moduleId + '-f' + formId,
                });
                return urlRoot + '#' + Util.objectToEncodedUrl(urlObject.toJson());
            };

            var reverse = hqImport("hqwebapp/js/urllib.js").reverse,
                app_id = initial_page_data('app_id'),
                module_id = initial_page_data('module_id'),
                form_id = initial_page_data('form_id');
            var cloudCareUrl = "";
            if (!COMMCAREHQ.toggleEnabled('USE_OLD_CLOUDCARE')) {
                cloudCareUrl = getFormplayerUrl(reverse("formplayer_single_app"), app_id, module_id, form_id);
            } else {
                cloudCareUrl = getCloudCareUrl(reverse("cloudcare_main"), app_id, module_id, form_id) + "?preview=true";
            }

            $("#cloudcare-preview-url").attr("href", cloudCareUrl);
            $('#cloudcare-preview-url').click(function() {
                ga_track_event('CloudCare', 'Click "Preview Form"');
                analytics.workflow("Clicked Preview Form");
                if (initial_page_data('user_age_in_days') === 0) {
                    ga_track_event('CloudCare', 'Clicked "Preview Form" within first 24 hours');
                    analytics.workflow('Clicked "Preview Form" within first 24 hours');
                }
            });
        }

        // Settings > Logic
        var $formFilter = $('#form-filter');
        if ($formFilter.length && initial_page_data('allow_form_filtering')) {
            $('#form-filter').koApplyBindings(new FormFilter());
        }

        if (initial_page_data('allow_form_workflow')) {
            var FormWorkflow = hqImport('app_manager/js/form_workflow.js').FormWorkflow;
            var labels = {};
            labels[FormWorkflow.Values.DEFAULT] = gettext("Home Screen");
            labels[FormWorkflow.Values.ROOT] = gettext("Module Menu");
            labels[FormWorkflow.Values.MODULE] = gettext("Module: ") + initial_page_data('module_name');
            if (initial_page_data('root_module_name')) {
                labels[FormWorkflow.Values.PARENT_MODULE] = gettext("Parent Module: ") + initial_page_data('root_module_name');
            }
            labels[FormWorkflow.Values.PREVIOUS_SCREEN] = gettext("Previous Screen");

            var options = {
                labels: labels,
                workflow: initial_page_data('post_form_workflow'),
                workflow_fallback: initial_page_data('post_form_workflow_fallback'),
            };

            if (COMMCAREHQ.toggleEnabled('FORM_LINK_WORKFLOW') || initial_page_data('uses_form_workflow')) {
                labels[FormWorkflow.Values.FORM] = gettext("Link to other form");
                options.forms = initial_page_data('linkable_forms');
                options.formLinks = initial_page_data('form_links');
                options.formDatumsUrl = hqImport('hqwebapp/js/urllib.js').reverse('get_form_datums');
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
        } else if (COMMCAREHQ.toggleEnabled('NO_VELLUM')) {
            $('#no-vellum').koApplyBindings({
                no_vellum: ko.observable(initial_page_data('no_vellum')),
            });
        }

        if (COMMCAREHQ.toggleEnabled('CUSTOM_INSTANCES')) {
            var customInstances = hqImport('app_manager/js/custom_intances.js').wrap({
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
