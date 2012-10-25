function ReportConfig(data) {
    var self = ko.mapping.fromJS(data, {
        'copy': ['filters']
    });

    self.isNew = ko.computed(function () {
        return typeof self._id === "undefined";
    });

    self.modalTitle = ko.computed(function () {
        return (self.isNew() ? 'New' : 'Edit') + ' Report Favorite' +
            (self.name() ? ': ' + self.name() : '');
    });

    self.unwrap = function () {
        var data = ko.mapping.toJS(self);
        data['report_slug'] = standardHQReport.slug;
        data['report_type'] = standardHQReport.type;
        data['subreport_slug'] = standardHQReport.subReportSlug;

        return data;
    },

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

function ReportConfigsViewModel(options) {
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
                for (var i = 0; i < self.reportConfigs().length; i++) {
                    if (ko.utils.unwrapObservable(self.reportConfigs()[i]._id) === config._id()) {
                        self.reportConfigs.splice(i, 1);
                        return;
                    }
                }
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

    // edit the config currently being viewed
    self.setConfigBeingEdited = function () {
        var filters = {},
            excludeFilters = ['startdate', 'enddate'];

        self.filterForm.find(":input").each(function () {
            var el = $(this),
                name = el.prop('name'),
                val = el.val();

                console.log(el);

            if (el.prop('type') === 'checkbox') {
                if (el.prop('checked') === true) {
                    if (!filters.hasOwnProperty(name)) {
                        filters[name] = [];
                    }

                    filters[name].push(val);
                }
            } else if (name && excludeFilters.indexOf(name) === -1) {
                filters[name] = val;
            }
        });

        self.configBeingViewed().filters = filters;
        self.configBeingEdited(self.configBeingViewed());
        self.modalSaveButton.state('save');
        
        /*$("#modal-body").find('date-picker').datepicker({
            changeMonth: true,
            changeYear: true,
            showButtonPanel: true,
            dateFormat: 'yy-mm-dd',
            maxDate: '0',
            numberOfMonths: 2
        });*/
    };

    self.unsetConfigBeingEdited = function () {
        self.configBeingEdited(undefined);
    };

    self.modalSaveButton = {
        state: ko.observable(),
        saveOptions: function () {
            return {
                url: options.saveUrl,
                type: 'post',
                data: JSON.stringify(self.configBeingEdited().unwrap()),
                dataType: 'json',
                success: function (data) {
                    self.addOrReplaceConfig(data);
                    self.unsetConfigBeingEdited();
                }
            };
        }
    };
}

$.fn.reportConfigEditor = function (options) {
    this.each(function(i, v) {
        options.filterForm = options.filterForm || $(v);
        var viewModel = new ReportConfigsViewModel(options);

        ko.applyBindings(viewModel, $(this).get(i));

        var data;
        if (options.initialItemID) {
            config = ko.utils.arrayFirst(viewModel.reportConfigs(), function(item) {
                return item._id() === options.initialItemID;
            });
            viewModel.setConfigBeingViewed(config);
        } else {
            viewModel.setConfigBeingViewed(new ReportConfig(options.defaultItem));
        }
    });
};

$.fn.reportConfigList = function (options) {
    this.each(function(i, v) {
        var viewModel = new ReportConfigsViewModel(options);
        ko.applyBindings(viewModel, $(this).get(i));
    });
};


var HQReport = function (options) {
    'use strict';
    var self = this;
    self.domain = options.domain;
    self.datespan = options.datespan;
    self.filterSet = options.filterSet || false;
    self.needsFilters = options.needsFilters || false;
    self.filterAccordion = options.filterAccordion || "#reportFilters";
    self.filterSubmitButton = options.filterSubmitButton || $('#paramSelectorForm button[type="submit"]');
    self.toggleFiltersButton = options.toggleFiltersButton || "#toggle-report-filters";
    self.exportReportButton = options.exportReportButton || "#export-report-excel";
    self.urlRoot = options.urlRoot;
    self.slug = options.slug;
    self.subReportSlug = options.subReportSlug;
    self.type = options.type;

    self.toggleFiltersCookie = self.domain+'.hqreport.toggleFilterState';
    self.datespanCookie = self.domain+".hqreport.filterSetting.test.datespan";

    self.initialLoad = true;

    self.init = function () {
        $(function () {
            checkFilterAccordionToggleState();

            $(self.exportReportButton).click(function (e) {
                var params = window.location.search.substr(1);
                var exportURL;
                e.preventDefault();
                if (params.length <= 1) {
                    if (self.loadDatespanFromCookie()) {
                        params = "startdate="+self.datespan.startdate+
                            "&enddate="+self.datespan.enddate;
                    }
                }
                window.location.href = window.location.pathname.replace(self.urlRoot,
                    self.urlRoot+'export/')+"?"+params;
            });

            self.resetFilterState();
            if (self.needsFilters) {
                self.filterSubmitButton.button('reset').addClass('btn-primary');
            }
        });
    };

    self.handleTabularReportCookies = function (reportDatatable) {
        var defaultRowsCookieName = self.domain+'.hqreport.tabularSetting.defaultRows',
            savedPath = window.location.pathname;
        var defaultRowsCookie = ''+$.cookie(defaultRowsCookieName);
        reportDatatable.defaultRows = parseInt(defaultRowsCookie) || reportDatatable.defaultRows;

        $(reportDatatable.dataTableElem).on('hqreport.tabular.lengthChange', function (event, value) {
            $.cookie(defaultRowsCookieName, value,
                {path: savedPath, expires: 2});
        });
    };

    self.saveDatespanToCookie = function () {
        if (self.datespan) {
            $.cookie(self.datespanCookie+'.startdate', self.datespan.startdate,
                {path: self.urlRoot, expires: 1});
            $.cookie(self.datespanCookie+'.enddate', self.datespan.enddate,
                {path: self.urlRoot, expires: 1});
        }
    };

    self.loadDatespanFromCookie = function () {
        if (self.datespan) {
            var cookie_startdate = $.cookie(self.datespanCookie+'.startdate'),
                cookie_enddate = $.cookie(self.datespanCookie+'.enddate'),
                load_success = false;

            if (cookie_enddate && cookie_startdate) {
                load_success = true;
                self.datespan.startdate = cookie_startdate;
                self.datespan.enddate = cookie_enddate;
            }
        }
        return load_success;
    };

    var checkFilterAccordionToggleState = function () {
        var _setShowFilterCookie = function (show) {
            var showStr = show ? 'in' : '';
            $.cookie(self.toggleFiltersCookie, showStr, {path: self.urlRoot, expires: 1});
        };
        
        if ($.cookie(self.toggleFiltersCookie) === null) {
            // default to showing filters
            _setShowFilterCookie(true);
        }
        $(self.filterAccordion).addClass($.cookie(self.toggleFiltersCookie));
        
        if ($.cookie(self.toggleFiltersCookie) == 'in')
            $(self.toggleFiltersButton).button('hide');
        else
            $(self.toggleFiltersButton).button('show');

        $(self.filterAccordion).on('hidden', function () {
            _setShowFilterCookie(false);
            $(self.toggleFiltersButton).button('show');
        });

        $(self.filterAccordion).on('show', function () {
            _setShowFilterCookie(true);
            $(self.toggleFiltersButton).button('hide');
        });

    };

    $(self.filterAccordion).on('hqreport.filter.datespan.startdate', function(event, value) {
        self.datespan.startdate = value;
    });

    $(self.filterAccordion).on('hqreport.filter.datespan.enddate', function(event, value) {
        self.datespan.enddate = value;
    });

    self.resetFilterState = function () {
        $('#paramSelectorForm fieldset button, #paramSelectorForm fieldset span[data-dropdown="dropdown"]').click(function() {
            $('#paramSelectorForm button[type="submit"]').button('reset').addClass('btn-primary');
        });
        $('#paramSelectorForm fieldset').change(function () {
            $('#paramSelectorForm button[type="submit"]').button('reset').addClass('btn-primary');
        });
    };


};
