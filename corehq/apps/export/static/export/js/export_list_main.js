hqDefine("export/js/export_list_main", function () {
    'use strict';

    var exportModel = function(options, pageOptions) {
        hqImport("hqwebapp/js/assert_properties").assert(pageOptions, ['is_deid', 'model_type']);

        _.each(['isAutoRebuildEnabled', 'isDailySaved', 'isFeed', 'showLink'], function (key) {
            options[key] = options[key] || false;
        });
        options.emailedExport = options.emailedExport || {};
        options.formname = options.formname || '';

        var mapping = {
            'copy': ["emailedExport"]
        };
        var self = ko.mapping.fromJS(options, mapping);

        self.isLocationSafeForUser = function () {
            return _.isEmpty(self.emailedExport) || self.emailedExport.isLocationSafeForUser;
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

        self.updateEmailedExportData = function (model) {
            var component = model.emailedExport;
            $('#modalRefreshExportConfirm-' + model.id() + '-' + component.groupId).modal('hide');
            component.updatingData = true;
            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse('update_emailed_export_data'),
                data: {
                    export_id: model.id(),
                    is_deid: pageOptions.is_deid,
                    model_type: pageOptions.model_type,
                },
                success: function (data) {
                    if (data.success) {
                        var exportType = hqImport('export/js/utils').capitalize(model.exportType());
                        hqImport('analytix/js/google').track.event(exportType + " Exports", "Update Saved Export", "Saved");
                        self.pollProgressBar(model);
                    }
                },
            });
        };

        self.updateDisabledState = function (model, e) {
            var component = model.emailedExport,
                $button = $(e.currentTarget);

            $button.disableButton();
            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse('toggle_saved_export_enabled'),
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
                    $('#modalEnableDisableAutoRefresh-' + model.id() + '-' + component.groupId).modal('hide');
                },
            });
        };

        return self;
    };

    var exportListModel = function(options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['exports', 'isDeid', 'modelType']);

        var self = {};

        self.modelType = options.modelType;
        self.isDeid = options.isDeid;
        self.exports = _.map(options.exports, function (e) {
            return exportModel(e, {
                is_deid: self.isDeid,
                model_type: self.modelType,
            });
        });
        self.myExports = _.filter(self.exports, function (e) { return !!e.my_export; });
        self.notMyExports = _.filter(self.exports, function (e) { return !e.my_export; });

        self.sendExportAnalytics = function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked Export button");
            return true;
        };

        // TODO: test
        // Polling
        self.pollProgressBar = function (exp) {
            exp.emailedExport.updatingData = false;
            exp.emailedExport.taskStatus = {
                'percentComplete': 0,
                'inProgress': true,
                'success': false,
            };
            var tick = function () {
                $.ajax({
                    method: 'GET',
                    url: hqImport("hqwebapp/js/initial_page_data").reverse("get_saved_export_progress"),
                    data: {
                        export_instance_id: exp.id(),
                        is_deid: self.isDeid,
                        model_type: self.modelType,
                    },
                    success: function (data) {
                        exp.emailedExport.taskStatus = data.taskStatus;
                        if (!data.taskStatus.success) {
                            // The first few ticks don't yet register the task
                            exp.emailedExport.taskStatus.inProgress = true;
                            setTimeout(tick, 1500);
                        } else {
                            exp.emailedExport.taskStatus.justFinished = true;
                        }
                    },
                });
            };
            tick();
        };
        _.each(self.exports, function (exp) {
            if (exp.emailedExport && exp.emailedExport.taskStatus && exp.emailedExport.taskStatus.inProgress) {
                self.pollProgressBar(exp);
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

        // HTML elements from filter form - it's not very knockout-y to manipulate directly
        self.$filterModal = $("#setFeedFiltersModal");
        self.$emwfCaseFilter = $("#id_emwf_case_filter");
        self.$emwfFormFilter = $("#id_emwf_form_filter");

        // Editing filters for a saved export
        self.formData = {};
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
            self.formData = newSelectedExport.emailedExport.filters;
            self.locationRestrictions(newSelectedExport.emailedExport.locationRestrictions);
            // select2s require programmatic update
            self.$emwfCaseFilter.select2("data", newSelectedExport.emailedExport.filters.emwf_case_filter);
            self.$emwfFormFilter.select2("data", newSelectedExport.emailedExport.filters.emwf_form_filter);
        });
        // TODO
        /*$scope.$watch("formData.date_range", function (newDateRange) {
            if (!newDateRange) {
                $scope.formData.date_range = "since";
            } else {
                self.formSubmitErrorMessage('');
            }
        });*/
        self.commitFilters = function () {
            var export_ = _.find(self.exports, function (e) { return e.id() === self.filterModalExportId(); });
            self.isSubmittingForm(true);

            // Put the data from the select2 into the formData object
            var exportType = export_.exportType;
            if (exportType === 'form') {
                self.formData.emwf_form_filter = self.$emwfFormFilter.select2("data");
                self.formData.emwf_case_filter = null;
            } else if (exportType === 'case') {
                self.formData.emwf_case_filter = self.$emwfCaseFilter.select2("data");
                self.formData.emwf_form_filter = null;
            }

            // TODO: test
            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse("commit_filters"),
                data: {
                    export_id: export_.id(),
                    form_data: self.formData,
                    is_deid: self.isDeid,
                    model_type: self.modelType,
                },
                success: function (data) {
                    self.isSubmittingForm(false);
                    if (data.success) {
                        self.formSubmitErrorMessage('');
                        export_.emailedExport.filters = self.formData;
                        self.pollProgressBar(export_);
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

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");

        $("#create-export").koApplyBindings(hqImport("export/js/create_export").createExportModel({
            model_type: initialPageData.get("model_type", true),
            drilldown_fetch_url: initialPageData.reverse('get_app_data_drilldown_values'),
            drilldown_submit_url: initialPageData.reverse('submit_app_data_drilldown_form'),
            page: {
                is_daily_saved_export: initialPageData.get('is_daily_saved_export', true),
                is_feed: initialPageData.get('is_feed', true),
                is_deid: initialPageData.get('is_deid', true),
                model_type: initialPageData.get('model_type', true),
            },
        }));
        $('#createExportOptionsModal').on('show.bs.modal', function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked New Export");
        });

        var modelType = initialPageData.get("model_type");
        $("#export-list").koApplyBindings(exportListModel({
            exports: initialPageData.get("exports"),
            modelType: modelType,
            isDeid: initialPageData.get('is_deid'),
        }));

        if (modelType === 'form') {
            hqImport('analytix/js/kissmetrix').track.event('Visited Export Forms Page');
        } else if (modelType === 'case') {
            hqImport('analytix/js/kissmetrix').track.event('Visited Export Cases Page');
        }
    });
});
