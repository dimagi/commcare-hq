/* globals hqDefine, ko */

hqDefine('domain/js/case-search-config.js', function () {
    'use strict';

    var module = {};

    /**
     * Create observables for current fuzzy properties config.
     * Modifies viewModel in-place
     * config mirrors the structure of corehq.apps.case_search.models.CaseSearchConfigJSON
     */
    module.getFuzzyPropertiesObservables = function (config) {
        var fuzzyProperties = [];
        if (config.hasOwnProperty('fuzzy_properties')) {
            // Build up observables for all case types and their properties
            for (var i = 0; i < config.fuzzy_properties.length; i++) {
                viewModel.fuzzyProperties.push({
                    field_id: 'case_type_' + i,
                    case_type: ko.observable(config.fuzzy_properties[i].case_type),
                    properties: ko.observableArray(config.fuzzy_properties[i].properties)
                });
            }
        } else {
            // New settings. Just create observables for an empty form
            fuzzyProperties.push({
                field_id: 'case_type_0',
                case_type: ko.observable(),  // Use Python naming convention because we will POST as-is
                properties: ko.observableArray([''])
            });
        }
        return fuzzyProperties;
    };

    /**
     * Returns a viewModel for domain/admin/case_search.html
     */
    module.CaseSearchConfig = function (options) {
        var self = this;
        var initialValues = options.values;
        self.caseTypes = options.caseTypes;

        var viewModel = {
            caseTypes: ko.observableArray(self.caseTypes),
            toggleEnabled: ko.observable(initialValues.enabled),
            fuzzyProperties: module.getFuzzyPropertiesObservables(initialValues.config)
        };
        viewModel.addProperty = function (data, event) {
            return true;
        };
        viewModel.removeProperty = function (data, event) {
            return true;
        };
        viewModel.addCaseType = function (data, event) {
            return true;
        };
        viewModel.removeCaseType = function (data, event) {
            return true;
        };

        return viewModel;
    };

    return module;
});
