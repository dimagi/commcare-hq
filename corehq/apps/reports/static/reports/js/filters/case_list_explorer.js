hqDefine("reports/js/filters/case_list_explorer", ['jquery', 'underscore', 'knockout'], function ($, _, ko) {
    'use strict';

    var applySuggestions = function (allSuggestions) {
        // Adds the required properties to filter the case type autocomplete dropdowns
        var self = this;
        self.currentCaseType = ko.observable('');
        $('#report_filter_case_type').on('change', function (e) {
            self.currentCaseType(e.val);
        });

        self.suggestedProperties = ko.computed(function () {
            if (self.currentCaseType() === '') {
                var filteredProperties = [];
                for (var i = 0; i < allSuggestions.length; i++) {
                    var suggestion = Object.assign({}, allSuggestions[i]);
                    if (suggestion.count === 1) {
                        filteredProperties.push(suggestion);
                    }
                    else if (_.findWhere(filteredProperties, {name: suggestion.name}) === undefined) {
                        if (suggestion.count !== undefined) {
                            suggestion.case_type = suggestion.count + " " + gettext("case types");
                        }
                        filteredProperties.push(suggestion);
                    }
                }
                return filteredProperties;
            }
            return _.filter(allSuggestions, function (prop) {
                return prop['case_type'] === self.currentCaseType() || prop['case_type'] === null;
            });
        });
    };

    var Property = function ($parent, name) {
        var self = {};
        self.name = ko.observable(name).trimmed();

        self.meta_type = ko.computed(function () {
            var value = _.find($parent.allSuggestions, function (prop) {
                return prop.name === self.name();
            });
            if (value) {
                return value.meta_type;
            }
            return null;
        });

        return self;
    };

    var casePropertyColumnsViewModel = function (initialColumns, allCaseProperties) {
        var self = {
            allSuggestions: allCaseProperties,
        };
        applySuggestions.call(self, allCaseProperties);

        self.properties = ko.observableArray();
        for (var i = 0; i < initialColumns.length; i++) {
            var initialColumn = initialColumns[i];
            self.properties.push(Property(self, initialColumn));
        }
        self.properties.subscribe(function () {
            // When reordering properties, trigger a change to enable the "Apply" button
            $('#fieldset_explorer_columns').trigger('change');
        });

        self.addProperty = function () {
            self.properties.push(Property(self, ''));
        };

        self.removeProperty = function (property) {
            self.properties.remove(property);
            $('#fieldset_explorer_columns').trigger('change');
        };

        self.allProperties = ko.computed(function () {

            return JSON.stringify(
                _.map(self.properties(), function (property) {
                    return property.name();
                })
            );
        });

        return self;
    };

    var caseSearchXpathViewModel = function (allSuggestions) {
        var self = {};
        applySuggestions.call(self, allSuggestions);
        self.query = ko.observable();
        return self;
    };

    return {
        casePropertyColumns: casePropertyColumnsViewModel,
        caseSearchXpath: caseSearchXpathViewModel,
    };
});
