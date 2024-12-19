/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/columns', [
    'jquery',
    'knockout',
    'underscore',
    'reports/v2/js/datagrid/column_filters',
    'analytix/js/kissmetrix',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    columnFilters,
    kissmetrics,
    initialPageData
) {
    'use strict';

    var columnModel = function (data) {
        var self = {};

        self.name = ko.observable(data.name);
        self.titlePlaceholder = ko.computed(function () {
            try {
                return _.map(self.name().replace('@', '').split('_'), function (name) {
                    return name.charAt(0).toUpperCase() + name.substring(1).toLowerCase();
                }).join(" ");
            } catch (e) {
                return gettext("Column Title");
            }
        });
        self.title = ko.observable(data.title);

        self.displayTitle = ko.computed(function () {
            return self.title() || self.titlePlaceholder();
        });

        self.width = ko.observable(data.width || 200);
        self.sort = ko.observable(data.sort);

        self.sortIconClass = ko.computed(function () {
            if (self.sort() === 'asc') {
                return 'glyphicon glyphicon-sort-by-attributes';
            }
            if (self.sort() === 'desc') {
                return 'glyphicon glyphicon-sort-by-attributes-alt';
            }
            return 'glyphicon glyphicon-sort';
        });

        self.clause = ko.observable(data.clause || 'all');

        self.appliedFilters = ko.observableArray(_.map(data.appliedFilters, function (filterData) {
            return columnFilters.appliedColumnFilter(filterData);
        }));

        self.hasFilters = ko.computed(function () {
            return self.appliedFilters().length > 0;
        });

        self.showAddFilter = ko.computed(function () {
            return self.appliedFilters().length === 0;
        });

        self.showAddExpression = ko.computed(function () {
            return self.appliedFilters().length > 0 && self.appliedFilters().length < 5;
        });

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        self.context = ko.computed(function () {
            return {
                name: self.name(),
                sort: self.sort(),
                clause: self.clause(),
                filters: _.map(self.appliedFilters(), function (filterData) {
                    return {
                        filterName: filterData.filterName(),
                        choiceName: filterData.choiceName(),
                        value: filterData.value() || '',
                    };
                }),
            };
        });

        self.getInitialNameValue = function () {
            if (!data.name) {
                return null;
            }
            return {
                id: data.name,
                text: data.name,
            };
        };

        return self;
    };

    var editColumnController = function (options) {
        var self = {};

        self.endpoint = options.endpoint;
        self.columnNameOptions = ko.observableArray();

        self.oldColumn = ko.observable();
        self.column = ko.observable();
        self.isNew = ko.observable();
        self.hasFilterUpdate = ko.observable(false);

        self.hideColumnFilterCondition = options.hideColumnFilterCondition;
        self.noDeleteColumnCondition = options.noDeleteColumnCondition;

        self.showColumnFilters = ko.computed(function () {
            if (!self.column()) {
                return false;
            }
            if (!self.column().name()) {
                return false;
            }
            if (!_.isFunction(self.hideColumnFilterCondition)) {
                return true;
            }
            return !self.hideColumnFilterCondition(self.column());
        });

        self.showColumnFilterPlaceholder = ko.computed(function () {
            if (!self.column()) {
                return false;
            }
            return self.column().name() === undefined || self.column().name().length === 0;
        });

        self.showDelete = ko.computed(function () {
            if (!_.isFunction(self.noDeleteColumnCondition)) {
                return true;
            }
            if (!self.column()) {
                return true;
            }
            return !self.noDeleteColumnCondition(self.column());
        });

        self.availableFilters = ko.observableArray(_.map(options.availableFilters, function (data) {
            return columnFilters.columnFilter(data);
        }));

        self.availableFilterNames = ko.computed(function () {
            return _.map(self.availableFilters(), function (filter) {
                return filter.name();
            });
        });

        self.filterTitleByName = _.object(_.map(self.availableFilters(), function (filter) {
            return [filter.name(), filter.title()];
        }));

        self.selectedFilter = ko.computed(function () {
            var selected = self.availableFilters()[0];

            if (self.column() && self.column().appliedFilters().length > 0) {
                _.each(self.availableFilters(), function (filter) {
                    if (filter.name() === self.column().appliedFilters()[0].filterName()) {
                        selected = filter;
                    }
                });
            }
            return selected;
        });

        self.isFilterText = ko.computed(function () {
            return self.selectedFilter().type() === 'text';
        });

        self.isFilterDate = ko.computed(function () {
            return self.selectedFilter().type() === 'date';
        });

        self.isFilterNumeric = ko.computed(function () {
            return self.selectedFilter().type() === 'numeric';
        });

        self.availableChoiceNames = ko.computed(function () {
            return _.map(self.selectedFilter().choices(), function (choice) {
                return choice.name();
            });
        });

        self.choiceTitleByName = ko.computed(function () {
            return _.object(_.map(self.selectedFilter().choices(), function (choice) {
                return [choice.name(), choice.title()];
            }));
        });

        self.init = function (reportContextObservable) {
            self.reportContext = reportContextObservable;
        };

        self.setNew = function () {
            self.oldColumn(undefined);

            if (self.isNew() && self.column()) {
                // keep state of existing add column progress
                self.column(columnModel(self.column().unwrap()));
            } else {
                self.column(columnModel({}));
                self.isNew(true);
                self.hasFilterUpdate(false);
            }

            kissmetrics.track.event("Clicked Add Column", {
                "Domain": initialPageData.get('domain'),
            });
        };

        self.set = function (existingColumn) {
            self.oldColumn(columnModel(existingColumn).unwrap());
            self.column(columnModel(existingColumn.unwrap()));
            self.isNew(false);
            self.hasFilterUpdate(false);
        };

        self.unset = function () {
            self.oldColumn(undefined);
            self.column(undefined);
            self.isNew(false);
            self.hasFilterUpdate(false);
        };

        self.addFilter = function () {
            self.column().appliedFilters.push(columnFilters.appliedColumnFilter({
                filterName: self.selectedFilter().name(),
                choiceName: self.selectedFilter().choices()[0].name(),
            }));
            self.hasFilterUpdate(true);
        };

        self.removeFilter = function (deletedFilter) {
            self.column().appliedFilters.remove(function (filter) {
                return filter === deletedFilter;
            });
            self.hasFilterUpdate(true);
        };

        self.updateFilterName = function () {
            var name = self.selectedFilter().name();
            _.each(self.column().appliedFilters(), function (filter) {
                if (filter.filterName() !== name) {
                    filter.filterName(name);
                }
            });
            self.hasFilterUpdate(true);
        };

        self.updateFilter = function () {
            self.hasFilterUpdate(true);
        };

        self.getData = function (data) {
            if (self.reportContext) {
                data.reportContext = JSON.stringify(self.reportContext());
            }
            return data;
        };

        self.isColumnValid = ko.computed(function () {
            if (self.column()) {
                return !!self.column().name();
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
