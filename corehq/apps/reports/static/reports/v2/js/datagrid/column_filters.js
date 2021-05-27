hqDefine('reports/v2/js/datagrid/column_filters', [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {
    'use strict';

    var columnFilterChoice = function (data) {
        /**
         * Matches the ChoiceMeta title / name specified by the column filter
         * @type {{
         *   title: "Human readable text",
         *   name: "unique name identifying the choice",
         * }}
         */
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);

        return self;
    };

    var columnFilter = function (data) {
        /**
         * Matches the ColumnFilter meta
         * @type {{
         *   title: "Human readable text",
         *   name: "unique name identifying the filter",
         *   type: "text, numeric, date",
         *   choices: "list of choices",
         * }}
         */
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);
        self.type = ko.observable(data.type);

        self.choices = ko.observableArray(_.map(data.choices, function (choiceData) {
            return columnFilterChoice(choiceData);
        }));

        return self;
    };

    var appliedColumnFilter = function (data) {
        /**
         * This will be the filter spec stored in the column model that will
         * be sent to the backend.
         * @type {{
         *   filterName: "unique name identifying the filter",
         *   choiceName: "unique name identifying the choice",
         *   value: "value to be applied alongside the filter",
         *   getExpression: a string describing the filter, used by analytics
         * }}
         */
        var self = {};

        self.filterName = ko.observable(data.filterName);
        self.choiceName = ko.observable(data.choiceName);
        self.value = ko.observable(data.value);

        self.getExpression = function () {
            return self.filterName() + " " + self.choiceName() + " " + self.value();
        };

        return self;
    };

    return {
        columnFilter: columnFilter,
        appliedColumnFilter: appliedColumnFilter,
    };
});
