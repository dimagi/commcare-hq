/* globals hqDefine, ko, $, _ */

hqDefine('domain/js/case-search-config.js', function () {
    'use strict';

    var module = {};

    var Property = function (name) {
        var self = this;
        self.name = ko.observable(name);
    };

    var CaseTypeProps = function (caseType, properties) {
        var self = this;

        self.caseType = ko.observable(caseType);
        self.properties = ko.observableArray(
            _.map(properties, function (name) { return new Property(name); })
        );

        self.addProperty = function () {
            self.properties.push(new Property(''));
        };
        self.removeProperty = function (property) {
            self.properties.remove(property);
        };
    };

    /**
     * Returns a viewModel for domain/admin/case_search.html
     */
    module.CaseSearchConfig = function (options) {
        var self = this;
        var initialValues = options.values;

        self.caseTypes = options.caseTypes;
        self.toggleEnabled = ko.observable(initialValues.enabled);
        self.fuzzyProperties = ko.observableArray();
        if (
            initialValues.config.hasOwnProperty('fuzzy_properties') &&
            initialValues.config.fuzzy_properties.length > 0
        ) {
            for (var i = 0; i < initialValues.config.fuzzy_properties.length; i++) {
                self.fuzzyProperties.push(new CaseTypeProps(
                    initialValues.config.fuzzy_properties[i].case_type,
                    initialValues.config.fuzzy_properties[i].properties
                ));
            }
        } else {
            self.fuzzyProperties.push(new CaseTypeProps('', ['']));
        }

        self.addCaseType = function () {
            self.fuzzyProperties.push(new CaseTypeProps('', ['']));
        };
        self.removeCaseType = function (caseType) {
            self.fuzzyProperties.remove(caseType);
        };

        self.submit = function (form) {
            var fuzzyProperties = [];
            for (var i = 0; i < self.fuzzyProperties().length; i++) {
                fuzzyProperties.push({
                    case_type: self.fuzzyProperties()[i].caseType(),
                    properties: _.map(
                        self.fuzzyProperties()[i].properties(),
                        function (property) { return property.name(); }
                    ),
                });
            }
            $.post({
                url: form.action, 
                data: {
                    'enable': self.toggleEnabled(),
                    'config': {'fuzzy_properties': fuzzyProperties},
                },
                success: function () {
                    // TODO: Watch changes. On success change Save button from btn-primary to btn-default
                },
            });
        };
    };

    return module;
});
