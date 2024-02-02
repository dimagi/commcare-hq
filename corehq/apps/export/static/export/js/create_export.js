/**
 * Controls the modal to create a new export.
 * Used on the basic Export Form/Case Data pages (not SMS), Daily Saved Exports, and Excel Dashboard Integration (feeds).
 *
 * Oriented around a drilldown form.
 *  For form-based exports: app type > app > module > form
 *  For case-based exports: app type > app > case type
 *
 * The daily saved and feeds pages aren't form/case specific,
 * so for those the drilldown starts with model type (form/case).
 */
hqDefine("export/js/create_export", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'analytix/js/kissmetrix',
    'select2/dist/js/select2.full.min',
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData,
    kissmetricsAnalytics
) {
    var createExportModel = function (options) {
        assertProperties.assert(options, ['drilldown_fetch_url', 'drilldown_submit_url', 'page'], ['model_type']);

        var self = {};

        self.isOData = initialPageData.get('is_odata', true);

        // This contains flags that distinguish the various pages that use this modal.
        // Note that there is both a page-level model type and an observable model type below, since model type
        // is static on the basic form/case export pages but is a user option on the daily saved & feed pages.
        assertProperties.assert(options.page, [
            'is_daily_saved_export', 'is_feed', 'is_deid', 'model_type', 'is_odata',
        ]);
        self.pageOptions = options.page;

        // Flags for the drilldown form, which is fetched via ajax on page initialization.
        self.isLoaded = ko.observable(false);
        self.isSubmitting = ko.observable(false);
        self.drilldownLoadError = ko.observable('');
        self.drilldownSubmissionError = ko.observable('');
        self.showNoAppsError = ko.observable(false);

        self.showDrilldown = ko.computed(function () {
            return !self.showNoAppsError() && !self.drilldownLoadError() && self.isLoaded() && !self.isSubmitting();
        });

        // Drilldown data
        self.staticModelType = !!options.model_type;
        self.modelType = ko.observable(options.model_type);
        self.appType = ko.observable();
        self.application = ko.observable();
        self.caseType = ko.observable();
        self.module = ko.observable();
        self.form = ko.observable();
        self.selectedAppData = ko.observable({});
        self.selectedFormData = ko.observable({});
        self.selectedFormName = ko.observable('');

        self.isCaseModel = ko.computed(function () {
            return self.modelType() === 'case';
        });
        self.isFormModel = ko.computed(function () {
            return self.modelType() === 'form';
        });

        // Behavior related to selecting an app type and an app
        self.hasSpecialAppTypes = ko.observable(false);
        self.hasNoCaseTypes = ko.observable(false);
        self.showAppType = ko.computed(function () {
            return self.hasSpecialAppTypes() || self.isFormModel();
        });

        self.showHasNoCaseTypes = ko.computed(function () {
            return self.hasNoCaseTypes() && self.application();
        });

        // Behavior related to selecting a form
        self.showMislabeled = ko.observable(false);
        self.showSuggestions = ko.observable(false);
        self.showAppDoesNotExist = ko.observable(false);
        self.showDuplicate = ko.observable(false);
        self.duplicatePossibilities = ko.observableArray();

        self.showSubmissionCount = ko.computed(function () {
            return self.modelType() === 'form' && !_.isEmpty(self.selectedFormData());
        });
        self.submissionCountText = ko.observable('');

        self.selectedFormData.subscribe(function (newValue) {
            var text = '';
            if (self.modelType() === 'form') {
                if (newValue.submissions === 1) {
                    text = gettext('<%- count %> form submission available.');
                } else {
                    text = gettext('<%- count %> form submissions available.');
                }
                text = _.template(text)({ count: newValue.submissions });
            }
            self.submissionCountText(text);

            self.showMislabeled(self.appType() === '_unknown' && !self.form() && !newValue.app_copy);
            self.showSuggestions(self.appType() === '_unknown' && !self.form() && !newValue.no_suggestions);
            self.showAppDoesNotExist(newValue.app_does_not_exist);
            self.showDuplicate(newValue.duplicate);
            self.duplicatePossibilities(newValue.possibilities);
            self.selectedFormName(newValue.is_user_registration ? gettext('User Registration') : newValue.name);
        });

        // Behavior related to initializing the drilldown form
        var drilldownDefaults = {
            model_type: '',
            app_type: 'all',
            application: null,
            module: null,
            form: null,
            case_type: null,
        };

        self.setAppTypes = function () {
            self.appType(drilldownDefaults.app_type);

            var $formElem = $('#id_app_type');
            if ($formElem.length > 0) {
                $formElem.select2({
                    data: self._app_types || [],
                    width: '100%',
                }).val(drilldownDefaults.app_type).trigger('change');
            }
        },
        self._initSelect2 = function (observable, fieldSlug) {
            return function (fieldData) {
                if (fieldSlug) {
                    observable('');
                    $('#div_id_' + fieldSlug).find("label").text(self._labels[fieldSlug]); 
                    var $formElem = $('#id_' + fieldSlug);
                    if ($formElem.length > 0) {
                        if ($formElem.hasClass("select2-hidden-accessible")) {
                            // checks to see if select2 has been initialized already.
                            // if it has, manually clear all existing HTML <options> on
                            // the <select> element directly. Otherwise, select2
                            // will prepend the data below to the existing
                            // <options>.
                            $formElem.html('');
                        }
                        $formElem.select2({
                            data: fieldData || [],
                            width: '100%',
                        }).val(drilldownDefaults[fieldSlug]).trigger('change');
                    }
                }
            };
        };
        self.setApps = self._initSelect2(self.application, 'application');
        self.setModules = self._initSelect2(self.module, 'module');
        self.setForms = self._initSelect2(self.form, 'form');
        self.setCaseTypes = self._initSelect2(self.caseType, 'case_type');

        // Behavior of drilldown itself (interactions between the dropdowns)
        self.appType.subscribe(function (newValue) {
            var appChoices = self._apps_by_type[newValue];
            self.setApps(appChoices);
            self.selectedAppData({});
            self.selectedFormData({});
            self.hasNoCaseTypes(false);
            self.setModules();
            self.setForms();
            self.setCaseTypes(self._all_case_types);
        });
        self.application.subscribe(function (newValue) {
            if (newValue) {
                if (self.modelType() === 'form') {
                    var moduleChoices = self._modules_by_app[newValue];
                    self.setModules(moduleChoices);
                    self.selectedFormData({});
                    self.setForms();
                } else {
                    var caseTypeChoices = self._all_case_types[newValue];
                    self.setCaseTypes(caseTypeChoices);
                    self.hasNoCaseTypes(_.isEmpty(caseTypeChoices));
                }
            } else {
                self.caseType('');
                self.module('');
            }

            var currentApp = _.find(self._apps_by_type[self.appType()], function (app) {
                return app.id === newValue;
            });
            if (!currentApp) {
                self.selectedAppData({});
            } else {
                self.selectedAppData(_.extend(currentApp.data, {
                    name: currentApp.text,
                }));
            }
        });
        self.module.subscribe(function (newValue) {
            if (newValue && self.application()) {
                var formChoices = self._forms_by_app_by_module[self.application()][newValue];
                self.setForms(formChoices);
            } else {
                self.form('');
            }
        });
        self.form.subscribe(function (newValue) {
            if (self.application() && self.module()) {
                var currentForm = _.find(self._forms_by_app_by_module[self.application()][self.module()], function (form) {
                    return form.id === newValue;
                });
                if (!currentForm) {
                    self.selectedFormData({});
                } else {
                    self.selectedFormData(_.extend(currentForm.data, {
                        name: currentForm.text,
                    }));
                }
            }
        });

        // Behavior related to validating and resetting the drilldown form
        self.isValid = ko.computed(function () {
            return self.modelType()
            && (
                (self.isCaseModel && self.caseType())
                || (
                    self.isFormModel()
                    && self.appType()
                    && self.application()
                    && self.module()
                    && self.form()
                )
            );
        });
        self.resetForm = function () {
            if (!self.isLoaded()) {
                return;
            }

            self.setAppTypes();
            self.setApps(self._apps_by_type.all || []);
            self.setModules();
            self.setForms();
            self.setCaseTypes(self._all_case_types);
            self.selectedAppData({});
            self.selectedFormData({});
            self.hasNoCaseTypes(false);
        };
        self.modelType.subscribe(self.resetForm);

        // Behavior related to submitting drilldown form
        self.showSubmit = ko.computed(function () {
            return !self.showNoAppsError() && !self.drilldownLoadError();
        });
        self.disableSubmit = ko.computed(function () {
            return !self.isValid() || self.isSubmitting();
        });

        self.handleSubmitForm = function () {
            self.isSubmitting(true);
            if (self.isOData) {
                kissmetricsAnalytics.track.event(
                    "[BI Integration] Clicked Add Odata Feed button",
                    {
                        "Feed Type": self.modelType(),
                    }
                );
                setTimeout(self.submitNewExportForm, 250);
            } else {
                self.submitNewExportForm();
            }

        };

        self.submitNewExportForm = function () {
            $.ajax({
                method: 'POST',
                url: options.drilldown_submit_url,
                data: {
                    is_daily_saved_export: self.pageOptions.is_daily_saved_export,
                    is_feed: self.pageOptions.is_feed,
                    is_deid: self.pageOptions.is_deid,
                    is_odata: self.pageOptions.is_odata,
                    model_type: self.pageOptions.model_type,
                    form_data: JSON.stringify({
                        model_type: self.modelType(),
                        app_type: self.appType(),
                        application: self.application(),
                        module: self.module(),
                        form: self.form(),
                        case_type: self.caseType(),
                    }),
                },
                success: function (data) {
                    if (data.success) {
                        window.location = data.url;
                    } else {
                        self.isSubmitting(false);
                        self.drilldownSubmissionError(data.error);
                    }
                },
                error: function () {
                    self.isSubmitting(false);
                    self.drilldownSubmissionError(gettext("There was an issue fetching data. Please check your internet connection."));
                },
            });
        };

        // Initialize drilldown on page load
        $.ajax({
            method: 'GET',
            url: options.drilldown_fetch_url,
            data: {
                is_deid: self.pageOptions.is_deid,
                is_odata: self.pageOptions.is_odata,
                model_type: self.pageOptions.model_type,
            },
            success: function (data) {
                self.showNoAppsError(data.app_types.length === 1 && data.apps_by_type.all.length === 0);
                if (!self.showNoAppsError()) {
                    self.hasSpecialAppTypes(data.app_types.length > 1);

                    self._labels = data.labels || {};
                    self._placeholders = data.placeholders || {};
                    self._app_types = data.app_types || [];
                    self._apps_by_type = data.apps_by_type || {};
                    self._modules_by_app = data.modules_by_app || {};
                    self._forms_by_app_by_module = data.forms_by_app_by_module || {};
                    if (data.case_types_by_app) {
                        self._all_case_types = data.case_types_by_app['_all_apps'];
                    } else {
                        self._all_case_types = {};
                    }

                    self.setAppTypes();
                    self.setApps(data.apps_by_type[self.appType()]);
                    self.setModules();
                    self.setForms();
                    self.setCaseTypes(self._all_case_types);
                }
                self.isLoaded(true);
            },
            error: function () {
                self.drilldownLoadError(gettext('There is an issue communicating with the server at this time.'));
                self.isLoaded(true);
            },
        });
        return self;
    };

    return {
        createExportModel: createExportModel,
    };
});
