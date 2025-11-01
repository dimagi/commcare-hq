import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import appManagerUtils from "app_manager/js/app_manager";
import noopMetrics from "analytix/js/noopMetrics";
import formWorkflow from "app_manager/js/forms/form_workflow";
import toggles from "hqwebapp/js/toggles";
import customInstancesModule from "app_manager/js/forms/custom_instances";
import "app_manager/js/nav_menu_media";
import "app_manager/js/forms/copy_form_to_app";
import "app_manager/js/forms/case_knockout_bindings";  // casePropertyAutocomplete and questionsSelect
import "app_manager/js/forms/case_config_ui";  // non-advanced modules only
import "app_manager/js/forms/advanced/case_config_ui";  // advanced modules only
import "app_manager/js/xpathValidator";
import "app_manager/js/custom_assertions";
import "hqwebapp/js/components/pagination";
import "hqwebapp/js/components/search_box";
import "hqwebapp/js/bootstrap3/knockout_bindings.ko";  // sortable binding
import casePropertyWarningViewModel from "data_dictionary/js/partials/case_property_warning";
import { customIconManager } from "app_manager/js/custom_icon";

appManagerUtils.setPrependedPageTitle("\u2699 ", true);
appManagerUtils.setAppendedPageTitle(gettext("Form Settings"));
appManagerUtils.updatePageTitle(initialPageData.get("form_name"));

function formFilterMatches(filter, substringMatches) {
    if (typeof(filter) !== 'string') {
        return false;
    }

    var result = false;
    $.each(substringMatches, function (index, sub) {
        result = result || filter.indexOf(sub) !== -1;
    });

    return result;
}

function formFilterModel() {
    var self = {};
    var patterns = initialPageData.get('form_filter_patterns');

    self.formFilter = ko.observable(initialPageData.get('form_filter'));

    self.caseReferenceNotAllowed = ko.computed(function () {
        var moduleUsesCase = initialPageData.get('all_other_forms_require_a_case') && initialPageData.get('form_requires') === 'case';
        if (!moduleUsesCase || (initialPageData.get('put_in_root') && !initialPageData.get('root_requires_same_case'))) {
            // We want to determine here if the filter expression references
            // any case but the user case.
            var filter = self.formFilter();
            if (typeof(filter) !== 'string') {
                return true;
            }

            $.each(patterns.usercase_substring, function (index, sub) {
                filter = filter.replace(sub, '');
            });

            if (formFilterMatches(filter, patterns.case_substring)) {
                return true;
            }
        }
        return false;
    });

    self.allowed = ko.computed(function () {
        return !self.formFilter() || !self.caseReferenceNotAllowed();
    });

    return self;
}

$(function () {
    // Form name
    $(document).on("inline-edit-save", function (e, data) {
        if (_.has(data.update, '.variable-form_name')) {
            appManagerUtils.updatePageTitle(data.update['.variable-form_name']);
            appManagerUtils.updateDOM(data.update);
        }
    });

    // Validation for build
    var setupValidation = appManagerUtils.setupValidation;
    setupValidation(initialPageData.reverse("validate_form_for_build"));

    // Analytics for renaming form
    $(".appmanager-edit-title").on('click', '.btn-primary', function () {
        noopMetrics.track.event("Renamed form from form settings page");
    });

    // Settings > Logic
    var $formFilter = $('#form-filter');
    if ($formFilter.length && initialPageData.get('allow_form_filtering')) {
        $('#form-filter').koApplyBindings(formFilterModel());
    }

    const labels = initialPageData.get('form_workflows');
    var options = {
        labels: labels,
        workflow: initialPageData.get('post_form_workflow'),
        workflow_fallback: initialPageData.get('post_form_workflow_fallback'),
    };

    if (_.has(labels, formWorkflow.FormWorkflow.Values.FORM)) {
        options.forms = initialPageData.get('linkable_forms');
        options.formLinks = initialPageData.get('form_links');
        options.formDatumsUrl = initialPageData.reverse('get_form_datums');
    }

    $('#form-workflow').koApplyBindings(new formWorkflow.FormWorkflow(options));

    // Settings > Advanced
    $('#auto-gps-capture').koApplyBindings({
        auto_gps_capture: ko.observable(initialPageData.get('auto_gps_capture')),
    });

    if (initialPageData.get('is_training_module')) {
        $('#release-notes-setting').koApplyBindings({
            is_release_notes_form: ko.observable(initialPageData.get('is_release_notes_form')),
            enable_release_notes: ko.observable(initialPageData.get('enable_release_notes')),
            is_allowed_to_be_release_notes_form: ko.observable(initialPageData.get('is_allowed_to_be_release_notes_form')),
            toggle_enable: function () {
                var allowed = this.is_release_notes_form();
                if (!allowed) {
                    this.enable_release_notes(false);
                }
                return true;
            },
        });
    }

    var $shadowParent = $('#shadow-parent');
    if ($shadowParent.length) {
        $shadowParent.koApplyBindings({
            shadow_parent: ko.observable(initialPageData.get('shadow_parent_form_id')),
        });
    }

    if (toggles.toggleEnabled('CUSTOM_INSTANCES')) {
        var customInstances = customInstancesModule.wrap({
            customInstances: initialPageData.get('custom_instances'),
        });
        $('#custom-instances').koApplyBindings(customInstances);
    }

    // Case Management > Data dictionary descriptions for case properties
    $('.property-description').popover();


    var $casePropertyWarning = $('#case-property-warning');
    if ($casePropertyWarning.length > 0) {
        const initialWarningData = initialPageData.get('case_property_warning');
        const warningViewModel = new casePropertyWarningViewModel(initialWarningData.limit);
        warningViewModel.updateViewModel(initialWarningData.type, initialWarningData.count);
        $casePropertyWarning.koApplyBindings(warningViewModel);
    }

    // Advanced > XForm > Upload
    $("#xform_file_input").change(function () {
        if ($(this).val()) {
            $("#xform_file_submit").show();
        } else {
            $("#xform_file_submit").hide();
        }
    }).trigger('change');

    customIconManager().init();
});
