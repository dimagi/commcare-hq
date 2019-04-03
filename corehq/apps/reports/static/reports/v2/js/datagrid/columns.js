/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/columns', [
    'jquery',
    'knockout',
    'underscore',
    'reports/v2/js/datagrid/filters',
], function (
    $,
    ko,
    _,
    filters
) {
    'use strict';

    var columnModel = function (data, availableFilters) {
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);
        self.width = ko.observable(data.width || 200);

        self.appliedFilters = ko.observableArray(_.map(data.appliedFilters, function (filterData) {
            var filterModel = filters.appliedColumnFilterModel(filterData);
            if (availableFilters) {
                filterModel.filter(ko.utils.arrayFirst(availableFilters(), function (item) {
                    return item.name() === filterModel.filter().name() && item.filterType() === filterModel.filter().filterType();
                }));
            }
            return filterModel;
        }));

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        self.getFilters = function () {
            return _.map(self.appliedFilters(), function (appliedFilter) {
                return {
                    propertyName: self.name(),
                    filterType: appliedFilter.filter().filterType(),
                    filterName: appliedFilter.filter().name(),
                    filterValue: appliedFilter.value(),
                };
            });
        };

        return self;
    };

    var editColumnController = function (options) {
        var self = {};

        self.endpoint = options.endpoint;

        self.availableFilters = ko.observableArray(_.map(options.availableFilters, function (data) {
            return filters.columnFilterModel(data);
        }));

        self.defaultFilterType = options.availableFilters[0].filterType;
        self.appliedFilterType = ko.observable();
        self.filterTitleByType = _.object(_.map(options.availableFilters, function (data) {
            return [data.filterType, data.filterTypeTitle];
        }));
        self.filterTypeOptions = ko.observableArray(_.keys(self.filterTitleByType));

        self.filterOptions = ko.computed(function () {
            return _.filter(self.availableFilters(), function (filter) {
                return filter.filterType() === self.appliedFilterType();
            })
        });

        self.columnNameOptions = ko.observableArray();

        self.oldColumn = ko.observable();
        self.column = ko.observable();
        self.isNew = ko.observable();
        self.hasFilterUpdate = ko.observable(false);

        self.init = function (reportContextObservable) {
            self.reportContext = reportContextObservable;
        };

        self.setNew = function () {
            self.reloadOptions();
            self.oldColumn(undefined);

            if (self.isNew() && self.column()) {
                // keep state of existing add column progress
                self.column(columnModel(self.column().unwrap(), self.availableFilters));
            } else {
                self.column(columnModel({}));
                self.isNew(true);
                self.hasFilterUpdate(false);
            }
            self.updateDefaultFilterType();
        };

        self.set = function (existingColumn) {
            self.reloadOptions();
            self.oldColumn(columnModel(existingColumn).unwrap());
            self.column(columnModel(existingColumn.unwrap(), self.availableFilters));
            self.isNew(false);
            self.hasFilterUpdate(false);
            self.updateDefaultFilterType();
        };

        self.unset = function () {
            self.oldColumn(undefined);
            self.column(undefined);
            self.isNew(false);
            self.hasFilterUpdate(false);
        };

        self.addFilter = function () {
            self.column().appliedFilters.push(filters.appliedColumnFilterModel({}));
            self.hasFilterUpdate(true);
        };

        self.removeFilter = function (filter) {
            self.column().appliedFilters.remove(function (listedFilter) {
                return listedFilter === filter;
            });
            self.hasFilterUpdate(true);
        };

        self.updateFilters = function () {
            self.hasFilterUpdate(true);
        };

        self.reloadOptions = function () {
            if (!self.reportContext) {
                throw new Error("Please call init() before calling loadOptions().");
            }

            $.ajax({
                url: self.endpoint.getUrl(),
                method: 'post',
                dataType: 'json',
                data: {
                    reportContext: JSON.stringify(self.reportContext()),
                },
            })
                .done(function (data) {
                    self.columnNameOptions(data.options);
                });
        };

        self.updateDefaultFilterType = function () {
            self.appliedFilterType((self.column().appliedFilters().length > 0) ? self.column().appliedFilters()[0].filter().filterType() : self.defaultFilterType);
        };

        self.isColumnValid = ko.computed(function () {
            if (self.column()) {
                return !!self.column().title() && !!self.column().name();
            }
            return false;
        });

        self.isSaveDisabled = ko.computed(function () {
            return !self.isColumnValid();
        });

        return self;
    };

    return {
        columnModel: columnModel,
        editColumnController: editColumnController,
    };
});
