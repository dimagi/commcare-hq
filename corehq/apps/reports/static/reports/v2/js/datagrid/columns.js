/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/columns', [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {
    'use strict';

    var columnModel = function (data) {
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);
        self.width = ko.observable(data.width || 200);

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        return self;
    };

    var editColumnController = function (options) {
        var self = {};

        self.endpoint = options.endpoint;
        self.reportContext = options.reportContext;
        self.columnNameOptions = ko.observableArray();

        self.oldColumn = ko.observable();
        self.column = ko.observable();
        self.isNew = ko.observable();

        self.setNew = function () {
            self.reloadOptions();
            self.oldColumn(undefined);

            if (self.isNew() && self.column()) {
                // keep state of existing add column progress
                self.column(columnModel(self.column().unwrap()));
            } else {
                self.column(columnModel({}));
                self.isNew(true);
            }
        };

        self.set = function (existingColumn) {
            self.reloadOptions();
            self.oldColumn(columnModel(existingColumn).unwrap());
            self.column(columnModel(existingColumn.unwrap()));
            self.isNew(false);
        };

        self.unset = function () {
            self.oldColumn(undefined);
            self.column(undefined);
            self.isNew(false);
        };

        self.reloadOptions = function () {
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
