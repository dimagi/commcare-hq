hqDefine("reports/js/filters/case_list_explorer", ['jquery', 'underscore', 'knockout'], function ($, _, ko) {
    'use strict';

    var applySuggestions = function (allSuggestions) {
        // Adds the required properties to filter the case type autocomplete dropdowns
        var self = this;
        self.currentCaseType = ko.observable('');
        $('#report_filter_case_type').on('change', function (e) {
            self.currentCaseType(e.currentTarget.value);
        });

        self.suggestedProperties = ko.computed(function () {
            if (self.currentCaseType() === '') {
                var filteredProperties = [];
                for (var i = 0; i < allSuggestions.length; i++) {
                    var suggestion = Object.assign({}, allSuggestions[i]);
                    if (suggestion.count === 1) {
                        filteredProperties.push(suggestion);
                    } else if (_.findWhere(filteredProperties, {name: suggestion.name}) === undefined) {
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

    var Property = function ($parent, name, label) {
        var self = {};
        self.name = ko.observable(name).trimmed();
        self.label = ko.observable(label).trimmed();

        self._value = function () {
            const valueList = _.filter($parent.allSuggestions, function (prop) {
                return prop.name === self.name();
            });
            if (valueList.length === 1) {
                return valueList[0];
            }
            return null;
        };

        self.meta_type = ko.computed(() => {
            var value = self._value();
            if (value) {
                return value.meta_type;
            }
            return null;
        });

        self.name.subscribe(() => {
            const value = self._value();
            if (value && value.label) {
                self.label(value.label);
            } else if (self.name()) {
                self.label(self.name());
            }
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
            self.properties.push(Property(self, initialColumn.name, initialColumn.label));
        }
        self.properties.subscribe(function () {
            // When reordering properties, trigger a change to enable the "Apply" button
            $('#fieldset_explorer_columns').trigger('change');
        });

        self.addProperty = function () {
            self.properties.push(Property(self, '', ''));
        };

        self.removeProperty = function (property) {
            self.properties.remove(property);
            $('#fieldset_explorer_columns').trigger('change');
        };

        self.allProperties = ko.computed(function () {

            return JSON.stringify(
                _.map(self.properties(), function (property) {
                    return {
                        name: property.name(),
                        label: property.label(),
                    };
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
