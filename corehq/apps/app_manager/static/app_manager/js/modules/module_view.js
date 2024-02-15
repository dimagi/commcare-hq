hqDefine("app_manager/js/modules/module_view", function () {
    $(function () {
        $('.case-type-dropdown').select2();
        $('.overwrite-danger').on("click", function () {
            hqImport('analytix/js/kissmetrix').track.event("Overwrite Case Lists/Case Details");
        });
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get,
            moduleBrief = initial_page_data('module_brief'),
            moduleType = moduleBrief.module_type,
            options = initial_page_data('js_options') || {};

        hqImport('app_manager/js/app_manager').setAppendedPageTitle(gettext("Menu Settings"));
        // Set up details
        if (moduleBrief.case_type) {
            var details = initial_page_data('details');
            for (var i = 0; i < details.length; i++) {
                var detail = details[i];
                var detailScreenConfigOptions = {
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
                    saveUrl: hqImport('hqwebapp/js/initial_page_data').reverse('edit_module_detail_screens'),
                    parentModules: initial_page_data('parent_case_modules'),
                    allCaseModules: initial_page_data('all_case_modules'),
                    caseTileTemplateOptions: options.case_tile_template_options,
                    caseTileTemplateConfigs: options.case_tile_template_configs,
                    childCaseTypes: detail.subcase_types,
                    fixture_columns_by_type: options.fixture_columns_by_type || {},
                    parentSelect: detail.parent_select,
                    fixtureSelect: detail.fixture_select,
                    multimedia: initial_page_data('multimedia_object_map'),
                };
                _.extend(detailScreenConfigOptions, options.search_config);
                var detailScreenConfig = hqImport("app_manager/js/details/screen_config")(detailScreenConfigOptions);

                var $list_home = $("#" + detail.type + "-detail-screen-config-tab");
                $list_home.koApplyBindings(detailScreenConfig);

                if (detail.long !== undefined) {
                    var $detail_home = $("#" + detail.type + "-detail-screen-detail-config-tab");
                    $detail_home.koApplyBindings(detailScreenConfig);
                }
            }
        }

        var originalCaseType = initial_page_data('case_type');
        var casesExist = false;
        var deprecatedCaseTypes = [];
        // If this async request is slow or fails, we will default to hiding the case type changed and
        // deprecated case type warnings.
        $.ajax({
            method: 'GET',
            url: hqImport('hqwebapp/js/initial_page_data').reverse('existing_case_types'),
            success: function (data) {
                casesExist = data.existing_case_types.includes(originalCaseType);
                deprecatedCaseTypes = data.deprecated_case_types;
                if (deprecatedCaseTypes.includes(originalCaseType)) {
                    showCaseTypeDeprecatedWarning();
                }
            },
        });

        // Validation for case type
        var showCaseTypeError = function (message) {
            var $caseTypeError = $('#case_type_error');
            $caseTypeError.css('display', 'block').removeClass('hide');
            $caseTypeError.text(message);
        };
        var hideCaseTypeError = function () {
            $('#case_type_error').addClass('hide');
        };

        var showCaseTypeChangedWarning = function () {
            if (casesExist) {
                $('#case_type_changed_warning').css('display', 'block').removeClass('hide');
                $('#case_type_form_group').addClass('has-error');
            }
        };
        var hideCaseTypeChangedWarning = function () {
            $('#case_type_changed_warning').addClass('hide');
            $('#case_type_form_group').removeClass('has-error');
        };

        var showCaseTypeDeprecatedWarning = function () {
            $('#case_type_deprecated_warning').css('display', 'block').removeClass('hide');
            $('#case_type_form_group').addClass('has-warning');
        };
        var hideCaseTypeDeprecatedWarning = function () {
            $('#case_type_deprecated_warning').addClass('hide');
            $('#case_type_form_group').removeClass('has-warning');
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
            if (!valueNoSpaces) {
                $el.closest('.form-group').addClass('has-error');
                showCaseTypeError(
                    gettext("Case type is required.")
                );
                return;
            }
            if (deprecatedCaseTypes.includes(value)) {
                showCaseTypeDeprecatedWarning();
            } else {
                hideCaseTypeDeprecatedWarning();
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

                if (value !== originalCaseType) {
                    showCaseTypeChangedWarning();
                } else {
                    hideCaseTypeChangedWarning();
                }
                if (deprecatedCaseTypes.includes(value)) {
                    showCaseTypeDeprecatedWarning();
                } else {
                    hideCaseTypeDeprecatedWarning();
                }
            }
        });

        $('#module-settings-form').on('saved-app-manager-form', function () {
            hideCaseTypeChangedWarning();
        });

        // Module filter
        var $moduleFilter = $('#module-filter');
        if ($moduleFilter.length) {
            $moduleFilter.koApplyBindings({xpath: initial_page_data("module_filter") || ''});
        }

        // UCR last updated tile
        var $reportContextTile = $('#report-context-tile');
        if ($reportContextTile.length) {
            $reportContextTile.koApplyBindings({
                report_context_tile: ko.observable(moduleBrief.report_context_tile),
            });
        }

        var lazyloadCaseListFields = $('#lazy-load-case-list-fields')
        if (lazyloadCaseListFields.length > 0) {
           lazyloadCaseListFields.koApplyBindings({
                lazy_load_case_list_fields: ko.observable(initial_page_data('lazy_load_case_list_fields')),
            });
        }


        // Registration in case list
        if ($('#case-list-form').length) {
            var caseListFormModel = function (originalFormId, formOptions, postFormWorkflow) {
                var self = {};

                self.caseListForm = ko.observable(originalFormId);
                self.caseListFormSettingsUrl = ko.computed(function () {
                    return hqImport("hqwebapp/js/initial_page_data").reverse("view_form", self.caseListForm());
                });
                self.postFormWorkflow = ko.observable(postFormWorkflow);
                self.endOfRegistrationOptions = ko.computed(function () {
                    if (!self.caseListForm() || formOptions[self.caseListForm()].is_registration_form) {
                        return [
                            {id: 'case_list', text: gettext('Go back to case list')},
                            {id: 'default', text: gettext('Proceed with registered case')},
                        ];
                    } else {
                        return [{id: 'case_list', text: gettext('Go back to case list')}];
                    }
                });

                self.formMissing = ko.computed(function () {
                    return self.caseListForm() && !formOptions[self.caseListForm()];
                });
                self.caseListForm.subscribe(function () {
                    if (self.caseListForm() && !formOptions[self.caseListForm()].is_registration_form) {
                        self.postFormWorkflow('case_list');
                    }
                });
                self.formHasEOFNav = ko.computed(function () {
                    if (!self.caseListForm()) {
                        return false;
                    }
                    var formData = formOptions[self.caseListForm()];
                    if (formData) {
                        return formData.post_form_workflow !== 'default';
                    }
                    return false;
                });

                var showMedia = function (formId) {
                    if (formId) {
                        $("#case_list_media").show();
                    } else {
                        $("#case_list_media").hide();
                    }
                };

                // Show or hide associated multimedia. Not done in knockout because
                // the multimedia section has its own separate set of knockout bindings
                showMedia(originalFormId);
                self.caseListForm.subscribe(showMedia);

                return self;
            };
            var case_list_form_options = initial_page_data('case_list_form_options');
            var caseListForm = caseListFormModel(
                case_list_form_options ? case_list_form_options.form.form_id : null,
                case_list_form_options ? case_list_form_options.options : [],
                case_list_form_options ? case_list_form_options.form.post_form_workflow : 'default'
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
            var ShadowModule = hqImport('app_manager/js/modules/shadow_module_settings').ShadowModule,
                shadowOptions = initial_page_data('shadow_module_options');
            $('#sourceModuleForms').koApplyBindings(new ShadowModule(
                shadowOptions.modules,
                shadowOptions.source_module_id,
                shadowOptions.excluded_form_ids,
                shadowOptions.form_session_endpoints,
                shadowOptions.shadow_module_version
            ));
        } else if (moduleType === 'advanced') {
            if (moduleBrief.has_schedule || hqImport('hqwebapp/js/toggles').toggleEnabled('VISIT_SCHEDULER')) {
                var VisitScheduler = hqImport('app_manager/js/visit_scheduler');
                var visitScheduler = VisitScheduler.moduleScheduler({
                    home: $('#module-scheduler'),
                    saveUrl: hqImport('hqwebapp/js/initial_page_data').reverse('edit_schedule_phases'),
                    hasSchedule: moduleBrief.has_schedule,
                    schedulePhases: initial_page_data('schedule_phases'),
                    caseProperties: initial_page_data('details')[0].properties,
                });
                visitScheduler.init();
            }

            $('#auto-select-case').koApplyBindings({
                auto_select_case: ko.observable(moduleBrief.auto_select_case),
            });
        }

        var setupValidation = hqImport('app_manager/js/app_manager').setupValidation;
        setupValidation(hqImport('hqwebapp/js/initial_page_data').reverse('validate_module_for_build'));

        // show display style options only when module configured to show module and then forms
        var $menu_mode = $('#put_in_root');
        var $display_style_container = $('#display_style_container');
        var update_display_view = function () {
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
