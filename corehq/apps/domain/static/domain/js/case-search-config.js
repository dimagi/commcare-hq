/* globals hqDefine, ko, $, _, COMMCAREHQ, hqImport */

hqDefine('domain/js/case-search-config', function () {
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

    var IgnorePatterns = function(caseType, caseProperty, regex){
        var self = this;

        self.caseType = ko.observable(caseType);
        self.caseProperty = ko.observable(caseProperty);
        self.regex = ko.observable(regex);
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
        for (var caseType in initialValues.fuzzy_properties){
            self.fuzzyProperties.push(new CaseTypeProps(
                caseType,
                initialValues.fuzzy_properties[caseType]
            ));
        }
        self.ignorePatterns = ko.observableArray();
        for (var i = 0; i < initialValues.ignore_patterns.length; i++){
            self.ignorePatterns.push(new IgnorePatterns(
                initialValues.ignore_patterns[i].case_type,
                initialValues.ignore_patterns[i].case_property,
                initialValues.ignore_patterns[i].regex
            ));
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

        self.addIgnorePatterns = function(){
            self.ignorePatterns.push(new IgnorePatterns('', '', ''));
            self.change();
        };
        self.removeIgnorePatterns = function(r){
            self.ignorePatterns.remove(r);
            self.change();
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged settings",
            save: function() {
                self.saveButton.ajax({
                    type: 'post',
                    url: hqImport("hqwebapp/js/urllib").reverse("case_search_config"),
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

                fuzzyProperties[caseType] = (fuzzyProperties[caseType] || []).concat(properties);
            }
            return {
                'enable': self.toggleEnabled(),
                'fuzzy_properties': fuzzyProperties,
                'ignore_patterns': _.map(self.ignorePatterns(), function(rc){
                    return {
                        'case_type': rc.caseType(),
                        'case_property': rc.caseProperty(),
                        'regex': rc.regex(),
                    };
                }),
            };
        };
    };

    return module;
});
