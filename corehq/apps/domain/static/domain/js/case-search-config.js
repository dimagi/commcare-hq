/* globals hqDefine, ko */

hqDefine('domain/js/case-search-config.js', function () {
    'use strict';

    var module = {};

    var CaseTypeProps = function (caseType, properties) {
        var self = this;
        self.case_type = ko.observable(caseType);
        self.properties = ko.observableArray(properties);

        self.addProperty = function (data, event) {
            self.properties.push('');
        };
        self.removeProperty = function (data, event) {
            // `data` is an empty string (the field's original value?).
            //self.properties.remove(data); // removes all properties.
        };
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
            fuzzyProperties: ko.observableArray()  // TODO: Why is this a bunch of empty strings?
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

        viewModel.addCaseType = function (data, event) {
            viewModel.fuzzyProperties.push(new CaseTypeProps('', ['']));
        };
        viewModel.removeCaseType = function (data, event) {
            viewModel.fuzzyProperties.remove(data);
        };

        viewModel.submit = function (form) {
            $.post(
                form.action,
                {
                    'enable': viewModel.toggleEnabled(),
                    'config': {
                        'fuzzy_properties': viewModel.fuzzyProperties()  // TODO: Strip the methods
                    }
                }
            ).success(function (data) {
                // TODO: Watch changes. On success change Save button from btn-primary to btn-default
            });
        };

        return viewModel;
    };

    return module;
});
