/* globals hqDefine, ko, $, _ */

hqDefine('domain/js/case-search-config.js', function () {
    'use strict';

    var module = {};

    var CaseTypeProps = function (caseType, properties) {
        var self = this;
        self.case_type = ko.observable(caseType);
        self.properties = ko.observableArray(properties);
        // TODO: ^^^ This observableArray isn't changing the values of the strings inside it.

        self.addProperty = function () {
            self.properties.push('');
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

        var viewModel = {
            caseTypes: options.caseTypes,
            toggleEnabled: ko.observable(initialValues.enabled),
            fuzzyProperties: ko.observableArray(),
        };
        if (initialValues.config.hasOwnProperty('fuzzy_properties')) {
            for (var i = 0; i < initialValues.config.fuzzy_properties.length; i++) {
                viewModel.fuzzyProperties.push(new CaseTypeProps(
                    initialValues.config.fuzzy_properties[i].case_type,
                    initialValues.config.fuzzy_properties[i].properties
                ));
            }
        } else {
            viewModel.fuzzyProperties.push(new CaseTypeProps('', ['']));
        }

        viewModel.addCaseType = function () {
            viewModel.fuzzyProperties.push(new CaseTypeProps('', ['']));
        };
        viewModel.removeCaseType = function (caseType) {
            viewModel.fuzzyProperties.remove(caseType);
        };

        viewModel.submit = function (form) {
            $.post(form.action, {
                'enable': viewModel.toggleEnabled(),
                'config': {'fuzzy_properties': _.pick(viewModel.fuzzyProperties(), 'case_type', 'properties')},
            }).success(function () {
                // TODO: Watch changes. On success change Save button from btn-primary to btn-default
            });
        };

        return viewModel;
    };

    return module;
});
