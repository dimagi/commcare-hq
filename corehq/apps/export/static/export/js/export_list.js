hqDefine("export/js/export_list", function () {
    var exportModel = function(options, pageOptions) {
        hqImport("hqwebapp/js/assert_properties").assert(pageOptions, ['is_deid', 'model_type', 'urls']);

        _.each(['isAutoRebuildEnabled', 'isDailySaved', 'isFeed', 'showLink'], function (key) {
            options[key] = options[key] || false;
        });
        options.formname = options.formname || '';

        hqImport("hqwebapp/js/assert_properties").assert(pageOptions.urls, ['poll', 'toggleEnabled', 'update']);

        var self = ko.mapping.fromJS(options);
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
            self.emailedExport.taskStatus.inProgress(true);
            self.emailedExport.taskStatus.success(false);
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
                        self.emailedExport.taskStatus.inProgress(data.taskStatus.inProgress);
                        self.emailedExport.taskStatus.success(data.taskStatus.success);
                        self.emailedExport.taskStatus.justFinished(data.taskStatus.justFinished);
                        if (!data.taskStatus.success) {
                            // The first few ticks don't yet register the task
                            self.emailedExport.taskStatus.inProgress(true);
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
                        var exportType = hqImport('export/js/utils').capitalize(model.exportType());
                        hqImport('analytix/js/google').track.event(exportType + " Exports", "Update Saved Export", "Saved");
                        model.pollProgressBar();
                    }
                },
            });
        };

        self.updateDisabledState = function (model, e) {
                $button = $(e.currentTarget);

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
                        var exportType = hqImport('export/js/utils').capitalize(model.exportType());
                        var event = (model.isAutoRebuildEnabled() ? "Disable" : "Enable") + " Saved Export";
                        hqImport('analytix/js/google').track.event(exportType + " Exports", event, "Saved");
                        model.isAutoRebuildEnabled(data.isAutoRebuildEnabled);
                    }
                    $button.enableButton();
                    $('#modalEnableDisableAutoRefresh-' + model.id() + '-' + model.emailedExport.groupId()).modal('hide');
                },
            });
        };

        return self;
    };

    var exportListModel = function(options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['exports', 'isDeid', 'modelType', 'urls']);

        var self = {};

        self.modelType = options.modelType;
        self.isDeid = options.isDeid;

        hqImport("hqwebapp/js/assert_properties").assert(options.urls, ['commitFilters', 'poll', 'toggleEnabled', 'update']);
        self.urls = options.urls;

        self.exports = _.map(options.exports, function (e) {
            return exportModel(e, {
                is_deid: self.isDeid,
                model_type: self.modelType,
                urls: _.pick(self.urls, 'poll', 'toggleEnabled', 'update'),
            });
        });
        self.myExports = _.filter(self.exports, function (e) { return !!e.my_export; });
        self.notMyExports = _.filter(self.exports, function (e) { return !e.my_export; });

        self.sendExportAnalytics = function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked Export button");
            return true;
        };

        _.each(self.exports, function (exp) {
            if (exp.hasEmailedExport && exp.emailedExport.taskStatus && exp.emailedExport.taskStatus.inProgress()) {
                exp.pollProgressBar();
            }
        });

        // Bulk export handling
        self.selectAll = function() {
            _.each(self.exports, function (e) { e.addedToBulk(true); });
        };
        self.selectNone = function() {
            _.each(self.exports, function (e) { e.addedToBulk(false); });
        };
        self.showBulkExportDownload = ko.observable(false);
        self.bulkExportList = ko.observable('');
        _.each(self.exports, function (e) {
            e.addedToBulk.subscribe(function (newValue) {
                // Determine whether or not to show bulk export download button & message
                if (newValue !== self.showBulkExportDownload()) {
                    self.showBulkExportDownload(!!_.find(self.exports, function (e) {
                        return e.addedToBulk();
                    }));
                }

                // Update hidden value of exports to download
                if (self.showBulkExportDownload()) {
                    self.bulkExportList(JSON.stringify(_.map(_.filter(self.exports, function (e) {
                        return e.addedToBulk();
                    }), function (e) {
                        return ko.mapping.toJS(e);
                    })));
                }
            });
        });

        // HTML elements from filter form - admittedly it's not very knockout-y to manipulate these directly
        self.$filterModal = $("#setFeedFiltersModal");
        self.$emwfCaseFilter = $("#id_emwf_case_filter");
        self.$emwfFormFilter = $("#id_emwf_form_filter");

        // Data from filter form
        self.emwfCaseFilter = ko.observableArray();
        self.emwfFormFilter = ko.observableArray();
        self.dateRange = ko.observable();
        self.days = ko.observable();
        self.startDate = ko.observable().extend({
            pattern: {
                message: gettext('Invalid date format'),
                params: '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$',
            },
        });
        self.endDate = ko.observable().extend({
            pattern: {
                message: gettext('Invalid date format'),
                params: '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$',
            },
        });

        // Editing filters for a saved export
        self.selectedExportModelType = ko.observable();
        self.filterModalExportId = ko.observable();
        self.locationRestrictions = ko.observableArray([]);  // List of location names. Export will be restricted to these locations.
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
            var newSelectedExport = _.find(self.exports, function (e) { return e.id() === newValue; });
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
            self.$emwfCaseFilter.select2("data", self.emwfCaseFilter());
            self.$emwfFormFilter.select2("data", self.emwfFormFilter());
        });
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
            var export_ = _.find(self.exports, function (e) { return e.id() === self.filterModalExportId(); });
            self.isSubmittingForm(true);

            var exportType = export_.exportType();
            if (exportType === 'form') {
                self.emwfFormFilter(self.$emwfFormFilter.select2("data"));
                self.emwfCaseFilter(null);
            } else if (exportType === 'case') {
                self.emwfCaseFilter(self.$emwfCaseFilter.select2("data"));
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
