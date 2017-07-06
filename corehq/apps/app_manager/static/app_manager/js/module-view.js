/*globals $, COMMCAREHQ, _, ko, django */
$(function () {
    var initial_page_data = hqImport('hqwebapp/js/initial_page_data.js').get,
        v2 = COMMCAREHQ.toggleEnabled('APP_MANAGER_V2'),
        moduleBrief = initial_page_data('module_brief'),
        moduleType = moduleBrief.module_type,
        options = initial_page_data('js_options') || {};

    hqImport('app_manager/js/app_manager.js').setAppendedPageTitle(django.gettext("Module Settings"));

    // Set up details
    if (!v2 || moduleBrief.case_type) {
        var state = hqImport('app_manager/js/detail-screen-config.js').state;
        var DetailScreenConfig = hqImport('app_manager/js/detail-screen-config.js').DetailScreenConfig;
        state.requires_case_details(moduleBrief.requires_case_details);

        var details = initial_page_data('details');
        for (var i = 0; i < details.length; i++) {
            var detail = details[i];
            var detailScreenConfig = DetailScreenConfig.init({
                module_id: moduleBrief.id,
                moduleUniqueId: moduleBrief.unique_id,
                state: {
                    type: detail.type,
                    short: detail.short,
                    long: detail.long,
                },
                sortRows: detail.sort_elements,
                model: detail.model,
                properties: detail.properties,
                lang: moduleBrief.lang,
                langs: moduleBrief.langs,
                saveUrl: hqImport('hqwebapp/js/urllib.js').reverse('edit_module_detail_screens'),
                parentModules: initial_page_data('parent_modules'),
                childCaseTypes: detail.subcase_types,
                fixture_columns_by_type: options.fixture_columns_by_type || {},
                parentSelect: detail.parent_select,
                fixtureSelect: detail.fixture_select,
                contextVariables: state,
                multimedia: initial_page_data('multimedia_object_map'),
                searchProperties: options.search_properties || [],
                includeClosed: options.include_closed,
                defaultProperties: options.default_properties || [],
                searchButtonDisplayCondition: options.search_button_display_condition,
                blacklistedOwnerIdsExpression: options.blacklisted_owner_ids_expression,
            });

            var $list_home = $("#" + detail.type + "-detail-screen-config-tab");
            $list_home.koApplyBindings(detailScreenConfig);

            if (detail.long !== undefined) {
                var $detail_home = $("#" + detail.type + "-detail-screen-detail-config-tab");
                $detail_home.koApplyBindings(detailScreenConfig);
            }
        }
    }

    // Validation for case type
    var showCaseTypeError = function(message) {
        var $caseTypeError = $('#case_type_error');
        $caseTypeError.css('display', 'block');
        $caseTypeError.text(message);
    };
    var hideCaseTypeError = function() {
        $('#case_type_error').css('display', 'none');
    };
    $('#case_type').on('textchange', function () {
        var $el = $(this),
            value = $el.val(),
            valueNoSpaces = value.replace(/ /g, '_');
        if (value !== valueNoSpaces) {
            var pos = $el.caret('pos');
            $el.val(valueNoSpaces);
            $el.caret('pos', pos);
        }
        if (v2 && !valueNoSpaces) {
            $el.closest('.form-group').addClass('has-error');
            showCaseTypeError(
                gettext("Case type is required.")
            );
            return;
        }
        if (!valueNoSpaces.match(/^[\w-]*$/g)) {
            $el.closest('.form-group').addClass('has-error');
            showCaseTypeError(
                gettext("Case types can only include the characters a-z, 0-9, '-' and '_'")
            );
        } else if (valueNoSpaces === 'commcare-user' && moduleType !== 'advanced') {
            $el.closest('.form-group').addClass('has-error');
            showCaseTypeError(
                gettext("'commcare-user' is a reserved case type. Please change the case type")
            );

        } else {
            $el.closest('.form-group').removeClass('has-error');
            hideCaseTypeError();
        }
    });

    // Module filter
    $(function () {
        var $moduleFilter = $('#module-filter');
        if ($moduleFilter.length) {
            $moduleFilter.koApplyBindings({xpath: initial_page_data("module_filter") || ''});
        }
    });

    // Registration in case list
    if ($('#case-list-form').length) {
        var CaseListForm = function (originalFormId, formOptions) {
            var self = this;

            self.caseListForm = ko.observable(originalFormId);
            self.formMissing = ko.computed(function() {
                return self.caseListForm() && !formOptions[self.caseListForm()];
            });

            // Show or hide associated multimedia. Not done in knockout because
            // the multimedia section has its own separate set of knockout bindings
            self.caseListForm.subscribe(function(form_id) {
                if (form_id) {
                    $("#case_list_media").show();
                } else {
                    $("#case_list_media").hide();
                }
            });
        };
        var case_list_form_options = initial_page_data('case_list_form_options');
            caseListForm = new CaseListForm(
                case_list_form_options ? case_list_form_options.form.form_id : null,
                case_list_form_options ? case_list_form_options.options : []
            );
        $('#case-list-form').koApplyBindings(caseListForm);

        // Reset save button after bindings
        // see http://manage.dimagi.com/default.asp?145851
        var $form = $('#case-list-form').closest('form'),
            $button = $form.find('.save-button-holder').data('button');
        $button.setStateWhenReady('saved');
    }

    if (moduleType === 'shadow') {
        // Shadow module checkboxes for including/excluding forms
        var ShadowModule = hqImport('app_manager/js/shadow-module-settings.js').ShadowModule,
            shadowOptions = initial_page_data('shadow_module_options');
        $('#sourceModuleForms').koApplyBindings(new ShadowModule(
            shadowOptions.modules,
            shadowOptions.source_module_id,
            shadowOptions.excluded_form_ids
        ));
    } else if (moduleType === 'advanced') {
        if (moduleBrief.has_schedule || COMMCAREHQ.toggleEnabled('VISIT_SCHEDULER')) {
            var VisitScheduler = hqImport('app_manager/js/visit-scheduler.js');
            var visitScheduler = new VisitScheduler.ModuleScheduler({
                home: $('#module-scheduler'),
                saveUrl: hqImport('hqwebapp/js/urllib.js').reverse('edit_schedule_phases'),
                hasSchedule: moduleBrief.has_schedule,
                schedulePhases: initial_page_data('schedule_phases'),
                caseProperties: initial_page_data('details')[0].properties,
            });
            visitScheduler.init();
        }

        $('#auto-select-case').koApplyBindings({
            auto_select_case: ko.observable(moduleBrief.auto_select_case),
        });
    } else if (moduleType === 'careplan') {
        var $container = $('#detail-screen-parent');
        if ($container.length) {
            var ParentSelect = hqImport('app_manager/js/detail-screen-config.js').ParentSelect;
            var parent_select_model = moduleBrief.parent_select;
            var parentSelect = new ParentSelect({
                active: parent_select_model.active,
                moduleId: parent_select_model.module_id,
                parentModules: initial_page_data('parent_modules'),
                lang: moduleBrief.lang,
                langs: moduleBrief.langs,
            });
            $container.koApplyBindings(parentSelect);
        }
    }

    $(function () {
        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport('hqwebapp/js/urllib.js').reverse('validate_module_for_build'));
    });

    $(function() {
        // show display style options only when module configured to show module and then forms
        var $menu_mode = $('#put_in_root');
        var $display_style_container = $('#display_style_container');
        var update_display_view = function() {
            if ($menu_mode.val() === 'false') {
                $display_style_container.show();
            } else {
                $display_style_container.hide();
            }
        };
        update_display_view();
        $menu_mode.on('change', update_display_view);
    });
});
