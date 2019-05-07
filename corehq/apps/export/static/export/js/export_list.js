/**
 *  This module contains the knockout models that control the "list" part of the exports list.
 *  This serves all export types: form vs case and exports vs daily saved vs dashboard feeds.
 *  It does NOT contain the logic for adding a new export, which is also done on the export list page.
 *
 *  There are three models in this file:
 *      exportModel represents an individual export: name, description, case type, etc.
 *      exportPanelModel represents a set of exports. Each of these is displayed in the UI as
 *          a panel with independent pagination.
 *      exportListModel represents the entire page. It contains one or more panels. It controls
 *          bulk export, which is a page-level action (you can select exports across panels to bulk export).
 *          It also controls filter editing (for daily saved / dashboard feeds).
 */
hqDefine("export/js/export_list", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/toggles',
    'clipboard/dist/clipboard',
    'analytix/js/google',
    'analytix/js/kissmetrix',
    'export/js/utils',
    'hqwebapp/js/validators.ko',        // needed for validation of startDate and endDate
    'hqwebapp/js/components.ko',        // pagination widget
    'select2/dist/js/select2.full.min',
], function (
    $,
    ko,
    _,
    assertProperties,
    toggles,
    Clipboard,
    googleAnalytics,
    kissmetricsAnalytics,
    utils
) {
    var exportModel = function (options, pageOptions) {
        assertProperties.assert(pageOptions, ['is_deid', 'model_type', 'urls']);

        _.each(['isAutoRebuildEnabled', 'isDailySaved', 'isFeed', 'showLink'], function (key) {
            options[key] = options[key] || false;
        });
        options.formname = options.formname || '';

        assertProperties.assert(pageOptions.urls, ['poll', 'toggleEnabled', 'update']);

        var self = ko.mapping.fromJS(options);
        self.prepareExportError = ko.observable('');
        self.hasEmailedExport = !!options.emailedExport;

        // Unwrap the values in the EMWF filters, turning them into plain {id: ..., text: ...} objects for use with select2
        if (self.hasEmailedExport) {
            self.emailedExport.filters.emwf_case_filter(_.map(self.emailedExport.filters.emwf_case_filter(), function (mw) {
                return _.mapObject(mw, function (observable) {
                    return observable();
                });
            }));
            self.emailedExport.filters.emwf_form_filter(_.map(self.emailedExport.filters.emwf_form_filter(), function (mw) {
                return _.mapObject(mw, function (observable) {
                    return observable();
                });
            }));
        }

        self.justUpdated = ko.computed(function () {
            if (self.emailedExport.taskStatus === undefined) {
                return false;
            }
            return self.emailedExport.taskStatus.justFinished() && self.emailedExport.taskStatus.success();
        });

        self.isLocationSafeForUser = function () {
            return !self.hasEmailedExport || self.emailedExport.isLocationSafeForUser();
        };

        self.downloadRequested = function (model, e) {
            var $btn = $(e.target);
            $btn.addClass('disabled');
            $btn.text(gettext('Download Requested'));
            return true;    // allow default click action to process so file is downloaded
        };
        self.copyLinkRequested = function (model, e) {
            model.showLink(true);
            var clipboard = new Clipboard(e.target, {
                target: function (trigger) {
                    return trigger.nextElementSibling;
                },
            });
            clipboard.onClick(e);
            clipboard.destroy();
        };

        // Polling
        self.pollProgressBar = function () {
            self.emailedExport.updatingData(false);
            self.emailedExport.taskStatus.percentComplete();
            self.emailedExport.taskStatus.started(true);
            self.emailedExport.taskStatus.success(false);
            self.emailedExport.taskStatus.failed(false);
            var tick = function () {
                $.ajax({
                    method: 'GET',
                    url: pageOptions.urls.poll,
                    data: {
                        export_instance_id: self.id(),
                        is_deid: self.isDeid,
                        model_type: self.modelType,
                    },
                    success: function (data) {
                        self.emailedExport.taskStatus.percentComplete(data.taskStatus.percentComplete);
                        self.emailedExport.taskStatus.started(data.taskStatus.started);
                        self.emailedExport.taskStatus.success(data.taskStatus.success);
                        self.emailedExport.taskStatus.failed(data.taskStatus.failed);
                        self.emailedExport.taskStatus.justFinished(data.taskStatus.justFinished);
                        if (!data.taskStatus.success && !data.taskStatus.failed) {
                            // The first few ticks don't yet register the task
                            self.emailedExport.taskStatus.started(true);
                            setTimeout(tick, 1500);
                        } else {
                            self.emailedExport.taskStatus.justFinished(true);
                        }
                    },
                });
            };
            tick();
        };

        self.updateEmailedExportData = function (model) {
            $('#modalRefreshExportConfirm-' + model.id() + '-' + model.emailedExport.groupId()).modal('hide');
            model.emailedExport.updatingData(true);
            $.ajax({
                method: 'POST',
                url: pageOptions.urls.update,
                data: {
                    export_id: model.id(),
                    is_deid: pageOptions.is_deid,
                    model_type: pageOptions.model_type,
                },
                success: function (data) {
                    if (data.success) {
                        var exportType = utils.capitalize(model.exportType());
                        googleAnalytics.track.event(exportType + " Exports", "Update Saved Export", "Saved");
                        model.pollProgressBar();
                    } else {
                        self.handleExportError(data);
                    }
                },
            });
        };

        self.handleExportError = function (data) {
            self.prepareExportError(data.error);
        };

        self.updateDisabledState = function (model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                method: 'POST',
                url: pageOptions.urls.toggleEnabled,
                data: {
                    export_id: model.id(),
                    is_auto_rebuild_enabled: model.isAutoRebuildEnabled(),
                    is_deid: pageOptions.is_deid,
                    model_type: pageOptions.model_type,
                },
                success: function (data) {
                    if (data.success) {
                        var exportType = utils.capitalize(model.exportType());
                        var event = (model.isAutoRebuildEnabled() ? "Disable" : "Enable") + " Saved Export";
                        googleAnalytics.track.event(exportType + " Exports", event, "Saved");
                        model.isAutoRebuildEnabled(data.isAutoRebuildEnabled);
                    }
                    $button.enableButton();
                    $('#modalEnableDisableAutoRefresh-' + model.id() + '-' + model.emailedExport.groupId()).modal('hide');
                },
            });
        };

        return self;
    };

    var exportPanelModel = function (options) {
        assertProperties.assert(options, ['header', 'isDailySavedExport', 'isDeid', 'isFeed', 'isOData', 'modelType', 'myExports', 'showOwnership', 'urls']);

        var self = _.extend({}, options);

        // Observable array because it'll be loaded via ajax
        self.exports = ko.observableArray([]);

        // Loading/error handling UI
        self.loadingErrorMessage = ko.observable('');
        self.isLoadingPanel = ko.observable(true);
        self.isLoadingPage = ko.observable(false);
        self.hasError = ko.observable(false);
        self.showError = ko.computed(function () {
            return !self.isLoadingPanel() && self.hasError();
        });
        self.showEmpty = ko.computed(function () {
            return !self.isLoadingPanel() && !self.hasError() && !self.exports().length;
        });
        self.showPagination = ko.computed(function () {
            return !self.isLoadingPanel() && !self.hasError() && self.exports().length;
        });

        self.totalItems = ko.observable(0);
        self.itemsPerPage = ko.observable();
        self.goToPage = function (page) {
            self.isLoadingPage(true);
            $.ajax({
                method: 'GET',
                url: self.urls.getExportsPage,
                data: {
                    is_deid: self.isDeid,
                    model_type: self.modelType,
                    is_daily_saved_export: self.isDailySavedExport ? 1 : 0,
                    is_feed: self.isFeed ? 1 : 0,
                    is_odata: self.isOData ? 1 : 0,
                    my_exports: self.myExports ? 1 : 0,
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.isLoadingPanel(false);
                    self.isLoadingPage(false);
                    self.totalItems(data.total);

                    self.exports(_.map(data.exports, function (e) {
                        return exportModel(e, {
                            is_deid: self.isDeid,
                            model_type: self.modelType,
                            urls: _.pick(self.urls, 'poll', 'toggleEnabled', 'update'),
                        });
                    }));

                    // Set up progress bar polling for any exports with email tasks running
                    _.each(self.exports(), function (exp) {
                        if (exp.hasEmailedExport && exp.emailedExport.taskStatus && exp.emailedExport.taskStatus.started()) {
                            exp.pollProgressBar();
                        }
                    });
                },
                error: function () {
                    self.isLoadingPanel(false);
                    self.hasError(true);
                },
            });
        };

        self.goToPage(1);

        return self;
    };

    var exportListModel = function (options) {
        assertProperties.assert(options, ['headers', 'isDailySavedExport', 'isDeid', 'isFeed', 'isOData', 'modelType', 'urls']);

        var self = {};

        self.modelType = options.modelType;
        self.isDeid = options.isDeid;
        self.isDailySavedExport = options.isDailySavedExport;
        self.isFeed = options.isFeed;
        self.isOData = options.isOData;

        assertProperties.assert(options.urls, ['commitFilters', 'getExportsPage', 'poll', 'toggleEnabled', 'update']);
        self.urls = options.urls;

        assertProperties.assert(options.headers, ['my_export_type', 'shared_export_type', 'export_type_caps_plural']);
        self.headers = options.headers;

        var panelOptions = _.omit(options, 'headers');
        self.panels = ko.observableArray([]);
        if (toggles.toggleEnabled("EXPORT_OWNERSHIP")) {
            self.panels.push(exportPanelModel(_.extend({}, panelOptions, {
                header: self.headers.my_export_type,
                showOwnership: true,
                myExports: true,
            })));
            self.panels.push(exportPanelModel(_.extend({}, panelOptions, {
                header: self.headers.shared_export_type,
                showOwnership: true,
                myExports: false,
            })));
        } else {
            self.panels.push(exportPanelModel(_.extend({}, panelOptions, {
                header: self.headers.export_type_caps_plural,
                showOwnership: false,
                myExports: false,       // value doesn't matter, but knockout will error if there isn't some value
            })));
        }
        self.exports = ko.computed(function () {
            return _.flatten(_.map(self.panels(), function (p) { return p.exports(); }));
        });

        self.sendExportAnalytics = function () {
            kissmetricsAnalytics.track.event("Clicked Export button");
            return true;
        };

        // Bulk export handling
        self.selectAll = function () {
            _.each(self.exports(), function (e) { e.addedToBulk(true); });
        };
        self.selectNone = function () {
            _.each(self.exports(), function (e) { e.addedToBulk(false); });
        };
        self.bulkExportDownloadCount = ko.computed(function () {
            return _.filter(self.exports(), function (e) { return e.addedToBulk(); }).length;
        });
        self.bulkExportList = ko.observable('');
        self.submitBulkExportDownload = function () {
            // Update hidden value of exports to download
            self.bulkExportList(JSON.stringify(_.map(_.filter(self.exports(), function (maybeSelectedExport) {
                return maybeSelectedExport.addedToBulk();
            }), function (maybeSelectedExport) {
                return ko.mapping.toJS(maybeSelectedExport);
            })));

            return true;
        };

        // HTML elements from filter form - admittedly it's not very knockout-y to manipulate these directly
        self.$filterModal = $("#setFeedFiltersModal");
        self.$emwfCaseFilter = $("#id_emwf_case_filter");
        self.$emwfFormFilter = $("#id_emwf_form_filter");

        // Data from filter form
        self.emwfCaseFilter = ko.observableArray().extend({notify: 'always'});
        self.emwfFormFilter = ko.observableArray().extend({notify: 'always'});
        self.dateRange = ko.observable().extend({notify: 'always'});
        self.days = ko.observable().extend({notify: 'always'});
        self.startDate = ko.observable().extend({
            notify: 'always',
            pattern: {
                message: gettext('Invalid date format'),
                params: '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$',
            },
        });
        self.endDate = ko.observable().extend({
            notify: 'always',
            pattern: {
                message: gettext('Invalid date format'),
                params: '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$',
            },
        });

        // Editing filters for a saved export
        self.selectedExportModelType = ko.observable();
        self.filterModalExportId = ko.observable();
        self.locationRestrictions = ko.observableArray([]).extend({notify: 'always'});  // List of location names. Export will be restricted to these locations.
        self.formSubmitErrorMessage = ko.observable('');
        self.dateRegex = '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]';
        self.isSubmittingForm = ko.observable(false);

        self.hasLocationRestrictions = ko.computed(function () {
            return self.locationRestrictions().length;
        });

        self.filterModalExportId.subscribe(function (newValue) {
            if (!newValue) {
                return;
            }
            var newSelectedExport = _.find(self.exports(), function (e) { return e.id() === newValue; });
            self.$filterModal.find("form")[0].reset();
            self.selectedExportModelType(newSelectedExport.exportType());
            self.emwfCaseFilter(newSelectedExport.emailedExport.filters.emwf_case_filter());
            self.emwfFormFilter(newSelectedExport.emailedExport.filters.emwf_form_filter());
            self.dateRange(newSelectedExport.emailedExport.filters.date_range());
            self.days(newSelectedExport.emailedExport.filters.days());
            self.startDate(newSelectedExport.emailedExport.filters.start_date());
            self.endDate(newSelectedExport.emailedExport.filters.end_date());
            self.locationRestrictions(newSelectedExport.emailedExport.locationRestrictions());

            // select2s require programmatic update
            self._initSelect2Value(self.$emwfCaseFilter, self.emwfCaseFilter());
            self._initSelect2Value(self.$emwfFormFilter, self.emwfFormFilter());
        });

        // $el is a select element backing a select2.
        // value is an array of objects, each with properties 'text' and 'id'
        self._initSelect2Value = function ($el, value) {
            $el.empty();
            _.each(value, function (item) {
                $el.append(new Option(item.text, item.id));
            });
            $el.val(_.pluck(value, 'id'));
            $el.trigger('change.select2');
        };

        self.showEmwfCaseFilter = ko.computed(function () {
            return self.selectedExportModelType() === 'case';
        });
        self.showEmwfFormFilter = ko.computed(function () {
            return self.selectedExportModelType() === 'form';
        });
        self.showDays = ko.computed(function () {
            return self.dateRange() === 'lastn';
        });
        self.showStartDate = ko.computed(function () {
            return self.dateRange() === 'range' || self.dateRange() === 'since';
        });
        self.showEndDate = ko.computed(function () {
            return self.dateRange() === 'range';
        });
        self.startDateHasError = ko.computed(function () {
            return !self.startDate.isValid();
        });
        self.endDateHasError = ko.computed(function () {
            return !self.endDate.isValid();
        });
        self.disableSubmit = ko.computed(function () {
            return self.showStartDate() && self.startDateHasError()
                || self.showEndDate() && self.endDateHasError();
        });
        self.commitFilters = function () {
            var export_ = _.find(self.exports(), function (e) { return e.id() === self.filterModalExportId(); });
            self.isSubmittingForm(true);

            var exportType = export_.exportType();
            if (exportType === 'form') {
                self.emwfFormFilter(self.$emwfFormFilter.val());
                self.emwfCaseFilter(null);
            } else if (exportType === 'case') {
                self.emwfCaseFilter(self.$emwfCaseFilter.val());
                self.emwfFormFilter(null);
            }

            $.ajax({
                method: 'POST',
                url: self.urls.commitFilters,
                data: {
                    export_id: export_.id(),
                    form_data: JSON.stringify({
                        emwf_case_filter: self.emwfCaseFilter(),
                        emwf_form_filter: self.emwfFormFilter(),
                        date_range: self.dateRange(),
                        days: self.days(),
                        start_date: self.startDate(),
                        end_date: self.endDate(),
                    }),
                    is_deid: self.isDeid,
                    model_type: self.modelType,
                },
                success: function (data) {
                    self.isSubmittingForm(false);
                    if (data.success) {
                        self.formSubmitErrorMessage('');
                        export_.emailedExport.filters.emwf_case_filter(self.emwfCaseFilter());
                        export_.emailedExport.filters.emwf_form_filter(self.emwfFormFilter());
                        export_.emailedExport.filters.date_range(self.dateRange());
                        export_.emailedExport.filters.days(self.days());
                        export_.emailedExport.filters.start_date(self.startDate());
                        export_.emailedExport.filters.end_date(self.endDate());
                        export_.pollProgressBar();
                        self.$filterModal.modal('hide');
                    } else {
                        self.formSubmitErrorMessage(data.error);
                    }
                },
                error: function () {
                    self.isSubmittingForm(false);
                    self.formSubmitErrorMessage(gettext("Problem saving dashboard feed filters"));
                },
            });
        };

        return self;
    };

    return {
        exportListModel: exportListModel,
    };
});
