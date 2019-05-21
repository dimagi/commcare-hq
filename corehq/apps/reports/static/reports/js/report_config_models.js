hqDefine("reports/js/report_config_models", [
    'jquery',
    'knockout',
    'underscore',
    'analytix/js/google',
    'reports/js/standard_hq_report',
    'jquery-ui/ui/datepicker',
], function (
    $,
    ko,
    _,
    googleAnalytics,
    standardHQReportModule
) {
    var reportConfig = function (data) {
        var self = ko.mapping.fromJS(data, {
            'copy': ['filters'],
        });

        self.error = ko.observable(false);

        self.isNew = ko.computed(function () {
            return typeof self._id === "undefined";
        });

        self.modalTitle = ko.computed(function () {
            return (self.isNew() ? 'New' : 'Edit') + ' Saved Report' +
                (self.name() ? ': ' + self.name() : '');
        });

        self.validate = function () {
            var date_range = self.date_range(),
                error = false;

            if (_.isEmpty(self.name())) {
                error = true;
            } else if (date_range === 'lastn') {
                var days = parseInt(self.days());
                if (!_.isNumber(days) || _.isNaN(days)) {
                    error = true;
                }
            } else if ((date_range === 'since' || date_range === 'range') && _.isEmpty(ko.utils.unwrapObservable(self.start_date))) {
                error = true;
            } else if (date_range === 'range' && _.isEmpty(ko.utils.unwrapObservable(self.end_date))) {
                error = true;
            }
            self.error(error);
            return !error;
        };

        self.unwrap = function () {
            var data = ko.mapping.toJS(self);
            var standardHQReport = standardHQReportModule.getStandardHQReport();
            if (standardHQReport.slug) {
                data['report_slug'] = standardHQReport.slug;
            }
            if (standardHQReport.type) {
                data['report_type'] = standardHQReport.type;
            }
            if (standardHQReport.subReportSlug) {
                data['subreport_slug'] = standardHQReport.subReportSlug;
            }
            return data;
        };

        self.dateRangeSubs = self.date_range.subscribe(function (newValue) {
            if (newValue === 'since' || newValue === 'range') {
                $('.date-picker').datepicker({
                    changeMonth: true,
                    changeYear: true,
                    showButtonPanel: true,
                    dateFormat: 'yy-mm-dd',
                });
            }
        });

        return self;
    };

    var reportConfigsViewModel = function (options) {
        var self = {};

        self.filterForm = options.filterForm;

        self.initialLoad = true;

        self.reportConfigs = ko.observableArray(ko.utils.arrayMap(options.items, function (item) {
            return reportConfig(item);
        }));

        self.configBeingViewed = ko.observable();

        self.configBeingEdited = ko.observable();

        self.filterHeadingName = ko.computed(function () {
            var config = self.configBeingViewed(),
                text = 'Report Filters';

            if (config && !config.isNew()) {
                text += ': ' + config.name();
            }

            return text;
        });

        self.addOrReplaceConfig = function (config) {
            for (var i = 0; i < self.reportConfigs().length; i++) {
                if (ko.utils.unwrapObservable(self.reportConfigs()[i]._id) === config._id()) {
                    self.reportConfigs.splice(i, 1, config);
                    return;
                }
            }

            // todo: alphabetize
            self.reportConfigs.push(config);
        };

        self.deleteConfig = function (config) {
            $.ajax({
                type: "DELETE",
                url: options.saveUrl + '/' + config._id(),
                success: function (data) {
                    window.location.reload();
                },
            });
        };

        self.setConfigBeingViewed = function (config) {
            self.configBeingViewed(config);
            if (self.initialLoad) {
                self.initialLoad = false;
            } else {
                window.location.href = config.url();
            }
        };

        self.setUserConfigurableConfigBeingViewed = function (config) {
            self.configBeingViewed(config);

            var filters = config.filters;
            update_filters = function () {
                for (var filter_name in filters) {
                    var val = filters[filter_name];
                    $('[name="' + filter_name + '"]').val(val);
                }
            };

            if (self.initialLoad) {
                self.initialLoad = false;
                update_filters();
            } else {
                update_filters();
                window.location.href = "?config_id=" + config._id();
            }
        };

        // edit the config currently being viewed
        self.setConfigBeingEdited = function (config) {
            var filters = {},
                excludeFilters = ['startdate', 'enddate', 'format', 'date'];
            if (self.filterForm) {
                self.filterForm.find(":input").each(function () {
                    var el = $(this),
                        name = el.prop('name'),
                        val = el.val(),
                        type = el.prop('type');

                    if (type === 'checkbox') {
                        if (el.prop('checked') === true) {
                            if (!filters.hasOwnProperty(name)) {
                                filters[name] = [];
                            }

                            filters[name].push(val);
                        }
                    } else if (type === 'radio') {
                        if (el.prop('checked') === true) {
                            filters[name] = val;
                        }
                    } else if (name && excludeFilters.indexOf(name) === -1) {
                        filters[name] = val;
                    }
                });
            } else {
                self.configBeingViewed(config);
                filters = config.filters;
            }

            self.configBeingViewed().filters = filters;

            var editedConfig = self.configBeingViewed();
            if (editedConfig.isNew()) {
                var daterangepicker = $("#filter_range").data('daterangepicker');
                if (daterangepicker) {
                    switch (daterangepicker.chosenLabel) {
                        case "Last 7 Days":
                            editedConfig.date_range("last7");
                            break;
                        case "Last 30 Days":
                            editedConfig.date_range("last30");
                            break;
                        case "Last Month":
                            editedConfig.date_range("lastmonth");
                            break;
                        case "Custom Range":
                            editedConfig.start_date = daterangepicker.startDate.format("YYYY-MM-DD");
                            editedConfig.end_date = daterangepicker.endDate.format("YYYY-MM-DD");
                            editedConfig.date_range("range");
                            break;
                        default:
                    }
                }
            }
            self.configBeingEdited(self.configBeingViewed());
            self.modalSaveButton.state('save');

            // Required to initialise datepicker if modal opened with date_range in ('since', 'range')
            $(".date-picker").datepicker({
                changeMonth: true,
                changeYear: true,
                showButtonPanel: true,
                dateFormat: 'yy-mm-dd',
            });
        };

        self.trackConfigBeingEdited = function (builderReportType) {
            googleAnalytics.track.event('Scheduled Reports', 'Create a saved report', '-');
            if (builderReportType) {
                googleAnalytics.track.event('Report Viewer', 'Save Report', builderReportType);
            }
        };

        self.unsetConfigBeingEdited = function () {
            self.configBeingEdited(undefined);
        };

        self.validate = function () {
            return self.configBeingEdited().validate();
        };

        self.modalSaveButton = {
            state: ko.observable(),
            saveOptions: function () {
                // TODO: Ideally the separator would be defined in one place. Right now it is
                //       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
                var separator = "\u001F",
                    config_data = self.configBeingEdited().unwrap();
                for (var key in config_data.filters) {
                    // remove null filters
                    if (config_data.filters.hasOwnProperty(key)) {
                        if (config_data.filters[key] === null) {
                            delete config_data.filters[key];
                        }
                        if (_.isArray(config_data.filters[key])) {
                            config_data.filters[key] = config_data.filters[key].join(separator);
                        }
                    }
                }
                return {
                    url: options.saveUrl,
                    type: 'post',
                    data: JSON.stringify(config_data),
                    dataType: 'json',
                    success: function (data) {
                        var newConfig = reportConfig(data);
                        self.addOrReplaceConfig(newConfig);
                        self.unsetConfigBeingEdited();
                        if (newConfig.report_slug == 'configurable') {
                            self.setUserConfigurableConfigBeingViewed(newConfig);
                        } else {
                            self.setConfigBeingViewed(newConfig);
                        }
                    },
                    beforeSend: function (jqXHR) {
                        var valid = self.validate();
                        if (!valid) {
                            jqXHR.abort();
                            $('#modal-save-button')[0].saveButton.setState('retry');
                        }
                    },
                };
            },
        };

        return self;
    };

    return {
        reportConfig: reportConfig,
        reportConfigsViewModel: reportConfigsViewModel,
    };
});
