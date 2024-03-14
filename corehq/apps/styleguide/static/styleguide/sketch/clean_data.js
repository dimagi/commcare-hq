hqDefine("styleguide/sketch/clean_data",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/bootstrap5/components.ko", // for pagination
    "hqwebapp/js/bootstrap5/validators.ko", // for validation
], function ($, ko, _, initialPageData) {
    'use strict';
    $(function () {
        let fakeData = function (data) {
            let self = {};
            self.slug = ko.observable(data.slug);
            self.originalValue = ko.observable(data.value);
            self.editedValue = ko.observable(data.value);
            self.isEdited = ko.computed(function () {
                return self.originalValue() !== self.editedValue();
            });
            return self;
        };

        let rowData = function (row, $table) {
            let self = {};
            self.id = ko.observable(row.id);
            self.isSelected = ko.observable(false);
            self.data = {};
            _.each(row.data, function (rawData) {
                self.data[rawData.slug] = new fakeData(rawData);
            });
            self.getSubmissionData = function () {
                return {
                    id: self.id(),
                    data: _.map(_.values(self.data), function (dataObs) {
                        return {'slug': dataObs.slug(), 'value': dataObs.editedValue()};
                    }),
                };
            };
            self.visibleData = ko.computed(function () {
                return _.map($table.visibleColumns(), function (column) {
                    return self.data[column.slug()];
                });
            });
            return self;
        };

        let Column = function (slug, name, isEditable) {
            let self = {};
            self.slug = ko.observable(slug);
            self.name = ko.observable(name);
            self.isEditable = ko.observable(isEditable);
            return self;
        };

        let Action = function (slug, name, options, transformationFunction) {
            let self = {};
            self.slug = ko.observable(slug);
            self.name = ko.observable(name);
            self.showFind = ko.observable(options.showFind);
            self.find = ko.observable().extend({
                // It's possible to stack validators like this:
                required: {
                    message: "Please specify a value.",
                    params: true,
                },
            });
            self.showReplace = ko.observable(options.showReplace);
            self.replace = ko.observable().extend({
                // It's possible to stack validators like this:
                required: {
                    message: "Please specify a value.",
                    params: true,
                },
            });
            self.showAdditionalFields = ko.computed(function () {
                return self.showFind() || self.showReplace();
            });
            // takes in value and action
            self.transformationFunction = transformationFunction;
            self.isActionValid = ko.computed(function () {
                return (self.find.isValid() || !self.showFind()) && (self.replace.isValid() || !self.showReplace());
            });
            return self;
        };

        let EditColumnForm = function () {
            let self = {};
            self.selectedColumnSlug = ko.observable().extend({
                // It's possible to stack validators like this:
                required: {
                    message: "Please select a column.",
                    params: true,
                },
            });
            self.selectedActionSlug = ko.observable().extend({
                // It's possible to stack validators like this:
                required: {
                    message: "Please select an action.",
                    params: true,
                },
            });
            self.availableActions = ko.observableArray([
                new Action('replace', "Replace", {
                    showReplace: true,
                }, function (value, action) {
                    return action.replace();
                }),
                new Action('find_replace', "Find & Replace", {
                    showReplace: true,
                    showFind: true,
                },  function (value, action) {
                    return value.replace(action.find(), action.replace());
                }),
                new Action('strip', "Strip Whitespaces", {}, function (value, action) {
                    return value.strip();
                }),
            ]);
            self.selectedAction = ko.computed(function () {
                if (self.selectedActionSlug()) {
                    return _.filter(self.availableActions(), function (action) {
                        return self.selectedActionSlug() === action.slug();
                    })[0];
                }
                return undefined;
            });
            self.isFormValid = ko.computed(function () {
                return (
                    self.selectedColumnSlug.isValid()
                    && self.selectedActionSlug.isValid()
                    && self.selectedAction()
                    && self.selectedAction().isActionValid()
                );
            });
            self.isSubmitDisabled = ko.computed(function () {
                return !self.isFormValid();
            });
            return self;
        };

        let paginationExample = function () {
            let self = {};

            self.rows = ko.observableArray();
            self.availableColumns = ko.observableArray([
                new Column('full_name', "Name", true),
                new Column('color', "Color", true),
                new Column('big_cat', "Big Cat", true),
                new Column('submitted_on', "Submitted On", false),
                new Column('app', "Application", false),
                new Column('status', "Status", false),
            ]);

            // we will change this in the UI
            self.visibleColumns = ko.observableArray(self.availableColumns());
            self.selectedRows = ko.computed(function () {
                return _.filter(self.rows(), function (row) {
                    return row.isSelected();
                });
            });
            self.isPreviewing = ko.observable(false);

            self.isCleanDataAllowed = ko.computed(function () {
                return self.selectedRows().length > 0;
            });
            self.isCleanDataButtonDisabled = ko.computed(function () {
                return !self.isCleanDataAllowed() || self.isPreviewing();
            });

            // edit context
            self.editableColumns = ko.computed(function () {
                return _.filter(self.visibleColumns(), function (col) {
                    return col.isEditable();
                });
            });
            self.editColumnForm = ko.observable(new EditColumnForm());
            self.resetEditColumnForm = function () {
                self.editColumnForm(new EditColumnForm());
            };
            self.previewEditColumnChanges = function () {
                if (!self.editColumnForm().isFormValid()) {
                    console.log("form is not valid");
                    return;
                }
                _.each(self.selectedRows(), function (row) {
                    let newValue = self.editColumnForm().selectedAction().transformationFunction(
                        row.data[self.editColumnForm().selectedColumnSlug()].originalValue(),
                        self.editColumnForm().selectedAction()
                    );
                    row.data[self.editColumnForm().selectedColumnSlug()].editedValue(newValue);
                });
                self.isPreviewing(true);
            };
            self.acceptChanges = function () {
                _.each(self.selectedRows(), function (row) {
                    row.data[self.editColumnForm().selectedColumnSlug()].originalValue(
                        row.data[self.editColumnForm().selectedColumnSlug()].editedValue()
                    );
                    row.isSelected(false);
                });
                self.stopPreviewing();
            };
            self.discardChanges = function () {
                _.each(self.selectedRows(), function (row) {
                    row.data[self.editColumnForm().selectedColumnSlug()].editedValue(
                        row.data[self.editColumnForm().selectedColumnSlug()].originalValue()
                    );
                    row.isSelected(false);
                });
                self.stopPreviewing();
            };
            self.stopPreviewing = function () {
                self.isPreviewing(false);
                self.resetEditColumnForm();
            };

            self.applyChangesToAllData = function () {
                $.ajax({
                    method: 'POST',
                    url: initialPageData.reverse("get_all_data_for_data_cleaning_prototype"),
                    data: {
                        all: true,
                    },
                    success: function (data) {
                        console.log(data.rows);
                        // todo do something with data.rows
                    },
                    error: function () {
                        console.log("error getting all data");
                    },
                });
            };

            self.getFormattedDataForSubmission = function (rows) {
                return JSON.stringify(_.map(rows, function (rowObj) {
                    return rowObj.getSubmissionData();
                }));
            };

            self.updateData = function (rows) {
                // todo not working
                $.ajax({
                    method: 'POST',
                    url: initialPageData.reverse("update_sprint_data"),
                    data: {
                        rows: self.getFormattedDataForSubmission(rows),
                    },
                    success: function (data) {
                        console.log(data);
                        // todo do something with data.rows
                    },
                    error: function () {
                        console.log("error getting all data");
                    },
                });
            };

            self.perPage = ko.observable();
            self.totalItems = ko.observable();
            self.itemsPerPage = ko.observable(100);

            self.showLoadingSpinner = ko.observable(true);
            self.error = ko.observable();

            self.selectAll = ko.observable(false);
            self.selectAll.subscribe(function (value) {
                _.each(self.rows(), function (row) {
                    row.isSelected(value);
                });
            });

            self.goToPage = function (page) {
                $.ajax({
                    method: 'POST',
                    url: initialPageData.reverse("get_data_for_data_cleaning_prototype"),
                    data: {
                        page: page,
                        limit: self.itemsPerPage(),
                    },
                    success: function (data) {
                        self.showLoadingSpinner(false);
                        self.totalItems(data.total);
                        self.rows.removeAll();
                        _.each(data.rows, function (row) {
                            self.rows.push(new rowData(row, self));
                        });
                        self.error(null);
                    },
                    error: function () {
                        self.showLoadingSpinner(false);
                        self.error(gettext(
                            "Could not load data. Please try again later or " +
                            "report an issue if this problem persists."
                        ));
                    },
                });
            };

            // Initialize with first page of data
            self.onPaginationLoad = function () {
                self.goToPage(1);
            };

            return self;
        };

        $("#clean-data-table-prototype").koApplyBindings(paginationExample());
    });
});
