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

        _.each(['isAutoRebuildEnabled', 'isDailySaved', 'isFeed', 'isOData', 'showLink'], function (key) {
            options[key] = options[key] || false;
        });
        options.formname = options.formname || '';

        assertProperties.assert(options, [
            'addedToBulk',
            'can_edit',
            'deleteUrl',
            'description',
            'downloadUrl',
            'editUrl',
            'emailedExport',
            'exportType',
            'filters',
            'formname',
            'id',
            'isDeid',
            'lastBuildDuration',
            'name',
            'owner_username',
            'sharing',
            'odataUrl',
        ], [
            'case_type',
            'isAutoRebuildEnabled',
            'isDailySaved',
            'isFeed',
            'isOData',
            'editNameUrl',
            'editDescriptionUrl',
            'showLink',
        ]);
        assertProperties.assert(pageOptions.urls, ['poll', 'toggleEnabled', 'update']);

        var self = ko.mapping.fromJS(options);

        self.showSavedFilters = !!options.filters;
        if (self.showSavedFilters) {
            // un-knockoutify case and form filter objects
            self.filters.emwf_case_filter(options.filters.emwf_case_filter);
            self.filters.emwf_form_filter(options.filters.emwf_form_filter);
        }

        self.hasEmailedExport = !!options.emailedExport;
        if (self.hasEmailedExport) {
            self.emailedExport = emailedExportModel(options.emailedExport, pageOptions, self.id(), self.exportType());
        }

        if (options.editNameUrl) {
            self.editNameUrl = options.editNameUrl;
        }
        if (options.editDescriptionUrl) {
            self.editDescriptionUrl = options.editDescriptionUrl;
        }

        if (options.isOData) {
            self.odataFeedUrl = options.odataUrl;
        }

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
            self.showLink(true);
            var clipboard = new Clipboard(e.target, {
                target: function (trigger) {
                    return trigger.nextElementSibling;
                },
            });
            clipboard.onClick(e);
            clipboard.destroy();
        };

        self.updateDisabledState = function (model, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                method: 'POST',
                url: pageOptions.urls.toggleEnabled,
                data: {
                    export_id: self.id(),
                    is_auto_rebuild_enabled: self.isAutoRebuildEnabled(),
                    is_deid: pageOptions.is_deid,
                    model_type: pageOptions.model_type,
                },
                success: function (data) {
                    if (data.success) {
                        var exportType = utils.capitalize(self.exportType());
                        var event = (self.isAutoRebuildEnabled() ? "Disable" : "Enable") + " Saved Export";
                        googleAnalytics.track.event(exportType + " Exports", event, "Saved");
                        self.isAutoRebuildEnabled(data.isAutoRebuildEnabled);
                    }
                    $button.enableButton();
                    $('#modalEnableDisableAutoRefresh-' + self.id() + '-' + self.emailedExport.groupId()).modal('hide');
                },
            });
        };

        return self;
    };

    var emailedExportModel = function (emailedExportOptions, pageOptions, exportId, exportType) {
        var self = ko.mapping.fromJS(emailedExportOptions);
        self.prepareExportError = ko.observable('');

        self.justUpdated = ko.computed(function () {
            if (self.taskStatus === undefined) {
                return false;
            }
            return self.taskStatus.justFinished() && self.taskStatus.success();
        });

        self.canUpdateData = ko.computed(function () {
            return (self.prepareExportError() ||
                    !(self.updatingData() || self.taskStatus && self.taskStatus.started()));
        });

        self.pollProgressBar = function () {
            self.updatingData(false);
            self.taskStatus.percentComplete();
            self.taskStatus.started(true);
            self.taskStatus.success(false);
            self.taskStatus.failed(false);
            var tick = function () {
                $.ajax({
                    method: 'GET',
                    url: pageOptions.urls.poll,
                    data: {
                        export_instance_id: exportId,
                        is_deid: pageOptions.is_deid,
                        model_type: pageOptions.model_type,
                    },
                    success: function (data) {
                        self.taskStatus.percentComplete(data.taskStatus.percentComplete);
                        self.taskStatus.started(data.taskStatus.started);
                        self.taskStatus.success(data.taskStatus.success);
                        self.taskStatus.failed(data.taskStatus.failed);
                        self.taskStatus.justFinished(data.taskStatus.justFinished);
                        if (!data.taskStatus.success && !data.taskStatus.failed) {
                            // The first few ticks don't yet register the task
                            self.taskStatus.started(true);
                            setTimeout(tick, 1500);
                        } else {
                            self.taskStatus.justFinished(true);
                        }
                    },
                });
            };
            tick();
        };

        self.updateData = function () {
            $('#modalRefreshExportConfirm-' + exportId + '-' + self.groupId()).modal('hide');
            self.updatingData(true);
            $.ajax({
                method: 'POST',
                url: pageOptions.urls.update,
                data: {
                    export_id: exportId,
                    is_deid: pageOptions.is_deid,
                    model_type: pageOptions.model_type,
                },
                success: function (data) {
                    if (data.success) {
                        var exportType_ = utils.capitalize(exportType);
                        googleAnalytics.track.event(exportType_ + " Exports", "Update Saved Export", "Saved");
                        self.pollProgressBar();
                    } else {
                        self.prepareExportError(data.error);
                    }
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
        self.hasData = ko.computed(function () {
            return !self.isLoadingPanel() && !self.hasError() && self.exports().length;
        });

        self.totalItems = ko.observable(0);
        self.itemsPerPage = ko.observable();
        self.goToPage = function (page) {
            if (self.hasData()) {
                self.fetchPage(page);
            }
        };
        self.fetchPage = function (page) {
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
                            exp.emailedExport.pollProgressBar();
                        }
                    });
                },
                error: function () {
                    self.isLoadingPanel(false);
                    self.hasError(true);
                },
            });
        };

        self.onPaginationLoad = function () {
            self.fetchPage(1);
        };

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
            self.emwfCaseFilter(newSelectedExport.filters.emwf_case_filter());
            self.emwfFormFilter(newSelectedExport.filters.emwf_form_filter());
            self.dateRange(newSelectedExport.filters.date_range());
            self.days(newSelectedExport.filters.days());
            self.startDate(newSelectedExport.filters.start_date());
            self.endDate(newSelectedExport.filters.end_date());
            if (newSelectedExport.hasEmailedExport) {
                self.locationRestrictions(newSelectedExport.emailedExport.locationRestrictions());
            }

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
                        export_.filters.emwf_case_filter(self.emwfCaseFilter());
                        export_.filters.emwf_form_filter(self.emwfFormFilter());
                        export_.filters.date_range(self.dateRange());
                        export_.filters.days(self.days());
                        export_.filters.start_date(self.startDate());
                        export_.filters.end_date(self.endDate());
                        if (export_.hasEmailedExport) {
                            export_.emailedExport.pollProgressBar();
                        }
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
