hqDefine("data_interfaces/js/case_dedupe_main", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',
], function ($, ko, _, initialPageData) {
    var caseDedupe = function (
        initialName,
        initialCaseType,
        caseTypeOptions,
        initialMatchType,
        initialCaseProperties,
        initialIncludeClosed,
        initialPropertiesToUpdate
    ) {
        var self = {};
        self.name = ko.observable(initialName);

        self.caseType = ko.observable(initialCaseType);
        self.caseTypeOptions = caseTypeOptions;

        self.matchType = ko.observable(initialMatchType);
        self.matchTypeText = ko.computed(function () {
            if (self.matchType() === "ANY") {
                return gettext("OR");
            }
            return gettext("AND");
        });
        self.matchTypeOptions = ["ALL", "ANY"];
        self.matchTypeOptionsText = function (item) {
            if (item === "ANY") {
                return gettext("True when ANY of the case properties match");
            }
            return gettext("True when ALL of the case properties match");
        };

        var caseProperty = function (name) {
            var self = {};
            self.name = ko.observable(name);
            return self;
        };
        self.caseProperties = ko.observableArray(_.map(initialCaseProperties, function (name) {
            return caseProperty(name);
        }));
        self.removeCaseProperty = function (item) {
            self.caseProperties.remove(item);
        };
        self.addCaseProperty = function () {
            self.caseProperties.push(caseProperty(''));
        };
        if (self.caseProperties().length === 0) {
            self.addCaseProperty();
        }
        self.serializedCaseProperties = ko.computed(function () {
            return ko.toJSON(self.caseProperties);
        });

        self.includeClosed = ko.observable(initialIncludeClosed);

        var propertyToUpdate = function (name, valueType, value) {
            var self = {};
            self.name = ko.observable(name);
            self.valueType = ko.observable(valueType);
            self.value = ko.observable(value);
            return self;
        };
        self.propertiesToUpdate = ko.observableArray(_.map(initialPropertiesToUpdate, function (property) {
            return propertyToUpdate(property.name, property.valueType, property.value);
        }));
        self.removePropertyToUpdate = function (item) {
            self.propertiesToUpdate.remove(item);
        };
        self.addPropertyToUpdate = function () {
            self.propertiesToUpdate.push(propertyToUpdate('', 'EXACT', ''));
        };
        self.serializedPropertiesToUpdate = ko.computed(function () {
            return ko.toJSON(self.propertiesToUpdate);
        });

        return self;
    };

    $(function () {
        $("#case-dedupe-rule-definition").koApplyBindings(
            caseDedupe(
                initialPageData.get('name'),
                initialPageData.get('case_type'),
                initialPageData.get('case_types'),
                initialPageData.get('match_type'),
                initialPageData.get('case_properties'),
                initialPageData.get('include_closed'),
                initialPageData.get('properties_to_update')
            )
        );
    });
});
