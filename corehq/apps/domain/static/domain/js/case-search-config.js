/* globals hqDefine, ko, $, _, COMMCAREHQ, hqImport */

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

        self.change = function(){
            self.saveButton.fire('change');
        };
        self.fuzzyProperties.subscribe(self.change);

        self.addCaseType = function () {
            self.fuzzyProperties.push(new CaseTypeProps('', ['']));
            self.change();
        };
        self.removeCaseType = function (caseType) {
            self.fuzzyProperties.remove(caseType);
            self.change();
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged settings",
            save: function() {
                self.saveButton.ajax({
                    type: 'post',
                    url: hqImport("hqwebapp/js/urllib.js").reverse("case_search_config"),
                    data: JSON.stringify(self.serialize()),
                    dataType: 'json',
                    contentType: "application/json; charset=utf-8",
                });
            },
        });

        self.serialize = function(){
            var fuzzyProperties = {};
            for (var i = 0; i < self.fuzzyProperties().length; i++) {
                var caseType = self.fuzzyProperties()[i].caseType(),
                    properties = _.map(
                        self.fuzzyProperties()[i].properties(),
                        function (property) { return property.name(); }
                    );

                if (fuzzyProperties[caseType]){
                    for (var propIdx in properties){
                        fuzzyProperties[caseType].push(properties[propIdx]);
                    }
                } else {
                    fuzzyProperties[caseType] = properties;
                }
            }
            return {
                'enable': self.toggleEnabled(),
                'fuzzy_properties': fuzzyProperties,
            };
        };
    };

    return module;
});
