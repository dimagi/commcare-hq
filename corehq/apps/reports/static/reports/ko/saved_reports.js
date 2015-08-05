var ReportConfig = function (data) {
    var self = ko.mapping.fromJS(data, {
        'copy': ['filters']
    });

    self.error = ko.observable(false);

    self.isNew = ko.computed(function () {
        return typeof self._id === "undefined";
    });

    self.modalTitle = ko.computed(function () {
        return (self.isNew() ? 'New' : 'Edit') + ' Saved Report' +
            (self.name() ? ': ' + self.name() : '');
    });

    self.validate = function() {
        var date_range = self.date_range(),
            error = false;

        if (_.isEmpty(self.name())) {
            error = true;
        }else if (date_range === 'lastn') {
            var days = parseInt(self.days());
            if (!_.isNumber(days) || _.isNaN(days)) {
                error = true;
            }
        } else if ((date_range === 'since' || date_range === 'range') && _.isEmpty(self.start_date())) {
            error = true;
        } else if (date_range === 'range' && _.isEmpty(self.end_date())) {
            error = true;
        }
        self.error(error);
        return !error;
    };

    self.unwrap = function () {
        var data = ko.mapping.toJS(self);
        if (null !== standardHQReport.slug) {
            data['report_slug'] = standardHQReport.slug;
        }
        if ("" !== standardHQReport.type) {
            data['report_type'] = standardHQReport.type;
        }
        if ("" !== standardHQReport.subReportSlug) {
            data['subreport_slug'] = standardHQReport.subReportSlug;
        }
        return data;
    };

    self.getDateUrlFragment = function () {
        // duplicated in reports/models.py
        var days, start_date, end_date = null,
            date_range = self.date_range(),
            today = new Date();

        if (date_range === 'since') {
            start_date = self.start_date();
            end_date = today;
        } else if (date_range === 'range') {
            start_date = self.start_date();
            end_date = self.end_date();
        } else {
            end_date = today;

            if (date_range === 'last7') {
                days = 7;
            } else if (date_range === 'last30') {
                days = 30;
            } else if (date_range === 'lastn') {
                days = self.days();
            } else {
                throw "Invalid date range.";
            }

            start_date = new Date();
            start_date.setDate(start_date.getDate() - days);
        }

        var dateToParam = function (date) {
            if (date && typeof date !== 'string') {
                return date.getFullYear() + '-' + (date.getMonth() + 1) + '-' + date.getDate();
            }
            return date;
        };

        end_date = dateToParam(end_date);
        start_date = dateToParam(start_date);

        return "startdate=" + start_date + "&enddate=" + end_date + "&";
    };

    return self;
};

var ReportConfigsViewModel = function (options) {
    var self = this;
    self.filterForm = options.filterForm;

    self.initialLoad = true;

    self.reportConfigs = ko.observableArray(ko.utils.arrayMap(options.items, function (item) {
        return new ReportConfig(item);
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

    self.addOrReplaceConfig = function (data) {
        var newConfig = new ReportConfig(data);

        for (var i = 0; i < self.reportConfigs().length; i++) {
            if (ko.utils.unwrapObservable(self.reportConfigs()[i]._id) === newConfig._id()) {
                self.reportConfigs.splice(i, 1, newConfig);
                return;
            }
        }

        // todo: alphabetize
        self.reportConfigs.push(newConfig);
    };

    self.deleteConfig = function (config) {
        $.ajax({
            type: "DELETE",
            url: options.saveUrl + '/' + config._id(),
            success: function (data) {
                window.location.reload();
            }
        });
    };

    self.setConfigBeingViewed = function (config) {
        self.configBeingViewed(config);

        var filters = config.filters,
            href = "?";


        if (self.initialLoad) {
            self.initialLoad = false;
        } else {
            for (var prop in filters) {
                if (filters.hasOwnProperty(prop)) {
                    // handle ufilter=0&ufilter=1&... etc
                    if ($.isArray(filters[prop])) {
                        for (var i = 0; i < filters[prop].length; i++) {
                            href += prop + '=' + filters[prop][i] + '&';
                        }
                    } else {
                        href += prop + '=' + filters[prop] + '&';
                    }
                }
            }

            window.location.href = href + config.getDateUrlFragment()
                + 'config_id=' + config._id();
        }
    };

    self.setUserConfigurableConfigBeingViewed = function (config) {
        self.configBeingViewed(config);

        var filters = config.filters;
        update_filters = function() {
            for (var filter_name in filters) {
                var val = filters[filter_name];
                $('[name="' + filter_name + '"]').val(val);
            }
        };

        if(self.initialLoad) {
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
            excludeFilters = ['startdate', 'enddate', 'format'];
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
        self.configBeingEdited(self.configBeingViewed());
        self.modalSaveButton.state('save');

        $(".save-date-picker").removeClass('hasDatepicker').datepicker({
            changeMonth: true,
            changeYear: true,
            showButtonPanel: true,
            dateFormat: 'yy-mm-dd',
            numberOfMonths: 2
        });
    };

    self.unsetConfigBeingEdited = function () {
        self.configBeingEdited(undefined);
    };

    self.validate = function() {
        return self.configBeingEdited().validate();
    };

    self.modalSaveButton = {
        state: ko.observable(),
        saveOptions: function () {
            var config_data = self.configBeingEdited().unwrap();
            var select2 = $("[data-ajax-select2]").map(function() {
                return $(this).attr('name');
            }).toArray();
            for (var key in config_data["filters"]) {
                // Make ajax select2 fields into lists so they serialize properly
                if (select2.indexOf(key) >= 0) {
                    config_data["filters"][key] = config_data["filters"][key].split(',');
                }
                // remove null filters
                if (config_data["filters"].hasOwnProperty(key)) {
                    if (config_data["filters"][key] === null) {
                        delete config_data["filters"][key];
                    }
                }
            }
            return {
                url: options.saveUrl,
                type: 'post',
                data: JSON.stringify(config_data),
                dataType: 'json',
                success: function (data) {
                    self.addOrReplaceConfig(data);
                    self.unsetConfigBeingEdited();
                },
                beforeSend: function(jqXHR) {
                    var valid = self.validate();
                    if (!valid) {
                        jqXHR.abort();
                    }
                }
            };
        }
    };
};

$.fn.reportConfigEditor = function (options) {
    this.each(function(i, v) {
        options.filterForm = options.filterForm || $(v);
        var viewModel = new ReportConfigsViewModel(options);

        ko.applyBindings(viewModel, $(this).get(i));

        viewModel.setConfigBeingViewed(new ReportConfig(options.defaultItem));
    });
};

$.fn.reportUserConfigurableConfigEditor = function (options) {
    this.each(function(i, v) {
        options.filterForm = options.filterForm || $(v);
        var viewModel = new ReportConfigsViewModel(options);

        ko.applyBindings(viewModel, $(this).get(i));

        viewModel.setUserConfigurableConfigBeingViewed(new ReportConfig(options.defaultItem));
    });
};

$.fn.reportConfigList = function (options) {
    this.each(function(i, v) {
        var viewModel = new ReportConfigsViewModel(options);
        ko.applyBindings(viewModel, $(this).get(i));
    });
};
