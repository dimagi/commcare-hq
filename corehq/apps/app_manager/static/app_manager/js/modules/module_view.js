hqDefine("app_manager/js/modules/module_view", [
    "jquery",
    "knockout",
    "underscore",
    "analytix/js/kissmetrix",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/app_manager",
    "app_manager/js/details/screen_config",
    "app_manager/js/modules/shadow_module_settings",
    "hqwebapp/js/toggles",
    "app_manager/js/visit_scheduler",   // advanced modules only
    "app_manager/js/custom_assertions",
    "select2/dist/js/select2.full.min",
    "app_manager/js/nav_menu_media",
    "app_manager/js/modules/case_list_setting",
    "hqwebapp/js/components/select_toggle",
    "hqwebapp/js/key-value-mapping",
    "app_manager/js/xpathValidator",
    "commcarehq",
], function (
    $,
    ko,
    _,
    kissmetrix,
    initialPageData,
    appManager,
    screenConfig,
    shadowModuleSettings,
    toggles,
    VisitScheduler,
) {
    $(function () {
        // Module name
        $(document).on("inline-edit-save", function (e, data) {
            if (_.has(data.update, '.variable-module_name')) {
                appManager.updatePageTitle(data.update['.variable-module_name']);
                appManager.updateDOM(data.update);
            }
        });

        $('.case-type-dropdown').select2();
        $('.overwrite-danger').on("click", function () {
            kissmetrix.track.event("Overwrite Case Lists/Case Details");
        });
        var moduleBrief = initialPageData.get('module_brief'),
            moduleType = moduleBrief.module_type,
            options = initialPageData.get('js_options') || {};

        appManager.setAppendedPageTitle(gettext("Menu Settings"));
        // Set up details
        if (moduleBrief.case_type) {
            var details = initialPageData.get('details');
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
                    saveUrl: initialPageData.reverse('edit_module_detail_screens'),
                    parentModules: initialPageData.get('parent_case_modules'),
                    allCaseModules: initialPageData.get('all_case_modules'),
                    caseTileTemplateOptions: options.case_tile_template_options,
                    caseTileTemplateConfigs: options.case_tile_template_configs,
                    childCaseTypes: detail.subcase_types,
                    fixture_columns_by_type: options.fixture_columns_by_type || {},
                    parentSelect: detail.parent_select,
                    fixtureSelect: detail.fixture_select,
                    multimedia: initialPageData.get('multimedia_object_map'),
                };
                _.extend(detailScreenConfigOptions, options.search_config);
                var detailScreenConfig = screenConfig(detailScreenConfigOptions);

                var $listHome = $("#" + detail.type + "-detail-screen-config-tab");
                $listHome.koApplyBindings(detailScreenConfig);

                if (detail.long !== undefined) {
                    var $detailHome = $("#" + detail.type + "-detail-screen-detail-config-tab");
                    $detailHome.koApplyBindings(detailScreenConfig);
                }
            }
        }

        var originalCaseType = initialPageData.get('case_type');
        var casesExist = false;
        var deprecatedCaseTypes = [];
        // If this async request is slow or fails, we will default to hiding the case type changed and
        // deprecated case type warnings.
        $.ajax({
            method: 'GET',
            url: initialPageData.reverse('existing_case_types'),
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
                    gettext("Case type is required."),
                );
                return;
            }
            if (deprecatedCaseTypes.includes(value)) {
                showCaseTypeDeprecatedWarning();
            } else {
                hideCaseTypeDeprecatedWarning();
            }
            if (appManager.valueIncludeInvalidCharacters(valueNoSpaces)) {
                $el.closest('.form-group').addClass('has-error');
                showCaseTypeError(
                    appManager.invalidCharErrorMsg,
                );
            } else if (appManager.valueIsReservedWord(valueNoSpaces) && moduleType !== 'advanced') {
                $el.closest('.form-group').addClass('has-error');
                showCaseTypeError(
                    appManager.reservedWordErrorMsg,
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
            $moduleFilter.koApplyBindings({xpath: initialPageData.get("module_filter") || ''});
        }

        // UCR last updated tile
        var $reportContextTile = $('#report-context-tile');
        if ($reportContextTile.length) {
            $reportContextTile.koApplyBindings({
                report_context_tile: ko.observable(moduleBrief.report_context_tile),
            });
        }

        var lazyloadCaseListFields = $('#lazy-load-case-list-fields');
        if (lazyloadCaseListFields.length > 0) {
            lazyloadCaseListFields.koApplyBindings({
                lazy_load_case_list_fields: ko.observable(initialPageData.get('lazy_load_case_list_fields')),
            });
        }

        var $showCaseListOptimizationsElement = $('#show_case_list_optimization_options');
        if ($showCaseListOptimizationsElement.length) {
            $showCaseListOptimizationsElement.koApplyBindings({
                show_case_list_optimization_options: ko.observable(
                    initialPageData.get('show_case_list_optimization_options'),
                ),
            });
        }


        // Registration in case list
        if ($('#case-list-form').length) {
            var caseListFormModel = function (originalFormId, formOptions, postFormWorkflow) {
                var self = {};

                self.caseListForm = ko.observable(originalFormId);
                self.caseListFormSettingsUrl = ko.computed(function () {
                    return initialPageData.reverse("view_form", self.caseListForm());
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
            var caseListFormOptions = initialPageData.get('case_list_form_options');
            var caseListForm = caseListFormModel(
                caseListFormOptions ? caseListFormOptions.form.form_id : null,
                caseListFormOptions ? caseListFormOptions.options : [],
                caseListFormOptions ? caseListFormOptions.form.post_form_workflow : 'default',
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
            const shadowOptions = initialPageData.get('shadow_module_options');
            $('#sourceModuleForms').koApplyBindings(new shadowModuleSettings.ShadowModule(
                shadowOptions.modules,
                shadowOptions.source_module_id,
                shadowOptions.excluded_form_ids,
                shadowOptions.form_session_endpoints,
                shadowOptions.shadow_module_version,
            ));
        } else if (moduleType === 'advanced') {
            if (moduleBrief.has_schedule || toggles.toggleEnabled('VISIT_SCHEDULER')) {
                var visitScheduler = VisitScheduler.moduleScheduler({
                    home: $('#module-scheduler'),
                    saveUrl: initialPageData.reverse('edit_schedule_phases'),
                    hasSchedule: moduleBrief.has_schedule,
                    schedulePhases: initialPageData.get('schedule_phases'),
                    caseProperties: initialPageData.get('details')[0].properties,
                });
                visitScheduler.init();
            }

            $('#auto-select-case').koApplyBindings({
                auto_select_case: ko.observable(moduleBrief.auto_select_case),
            });
        }

        appManager.setupValidation(initialPageData.reverse('validate_module_for_build'));

        // show display style options only when module configured to show module and then forms
        var $menuMode = $('#put_in_root');
        var $displayStyleContainer = $('#display_style_container');
        var updateDisplayView = function () {
            if ($menuMode.val() === 'false') {
                $displayStyleContainer.show();
            } else {
                $displayStyleContainer.hide();
            }
        };
        updateDisplayView();
        $menuMode.on('change', updateDisplayView);
    });
});
