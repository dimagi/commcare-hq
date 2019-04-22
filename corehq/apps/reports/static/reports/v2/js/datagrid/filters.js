hqDefine('reports/v2/js/datagrid/filters', [
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
         *   choices: "list of choices",
         * }}
         */
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);
        self.choices = ko.observableArray(_.map(data.choices, function (choiceData) {
            return columnFilterChoice(choiceData);
        }));

        return self;
    };

    return {
        columnFilter: columnFilter,
    };
});
