hqDefine("data_interfaces/js/case_dedupe_main", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_property_input',
    'data_interfaces/js/case_rule_criteria',
    'hqwebapp/js/widgets',
], function (
    $,
    ko,
    _,
    initialPageData,
    casePropertyInput,
    CaseRuleCriteria
) {

    /*
    PropertyManager exists to make sure that available properties are updated and unique.
    For example, if a case type contains A, B, and C properties, this class ensures
    that if C is selected, further options will only show A and B.
    */
    const PropertyManager = function (caseType, selectedProperties, initialPropertyMap) {
        const self = {};
        self.caseType = caseType;
        self.selectedProperties = selectedProperties;
        self.availablePropertyMap = ko.observable(clonePropertyMap(initialPropertyMap));

        self.addProperty = function (property) {
            self.selectedProperties.push(property);

            if (property.name()) {
                let currentProperties = self.availablePropertyMap()[self.caseType()];
                currentProperties = reserveProperties([property.name()], currentProperties);
                rebuildPropertyMap(currentProperties);
            }
        };

        self.removeProperty = function (property) {
            self.selectedProperties.remove(property);

            let currentProperties = self.availablePropertyMap()[self.caseType()];
            currentProperties = restoreProperty(property.name(), currentProperties);

            rebuildPropertyMap(currentProperties);
        };

        self.updatePropertyValue = function (oldValue, newValue) {
            let currentProperties = self.availablePropertyMap()[self.caseType()];
            currentProperties = reserveProperties([oldValue], currentProperties);
            currentProperties = restoreProperty(newValue, currentProperties);

            rebuildPropertyMap(currentProperties);
        };

        self.caseType.subscribe(handleCaseTypeChange);
        function handleCaseTypeChange(caseType) {
            if (!caseType) {
                return;
            }

            resetAvailableProperties();

            const selectedNames = self.selectedProperties().map(function (prop) {
                return prop.name();
            });

            let currentProperties = self.availablePropertyMap()[caseType];
            currentProperties = reserveProperties(selectedNames, currentProperties);
            rebuildPropertyMap(currentProperties);
        }

        function resetAvailableProperties() {
            const originalPropertyMap = clonePropertyMap(initialPropertyMap);
            self.availablePropertyMap(originalPropertyMap);
        }

        function clonePropertyMap(originalMap) {
            const clone = {};
            for (const key in originalMap) {
                clone[key] = originalMap[key].slice();
            }

            return clone;
        }

        function propertyExistsInOriginalMap(propName) {
            const originalProperties = initialPropertyMap[self.caseType()];

            return (originalProperties.indexOf(propName) !== -1);
        }

        function rebuildPropertyMap(changedCategory) {
            const caseType = self.caseType();
            const existingMap = self.availablePropertyMap();
            changedCategory.sort();
            existingMap[caseType] = changedCategory;
            self.availablePropertyMap(existingMap);
        }

        function restoreProperty(propName, currentProperties) {
            if (!propName || !propertyExistsInOriginalMap(propName)) {
                // do not put custom properties back into the map
                return currentProperties;
            }

            currentProperties.push(propName);

            return currentProperties;
        }

        function reserveProperties(propertyNames, currentProperties) {
            propertyNames.forEach(function (propName) {
                const foundIndex = currentProperties.indexOf(propName);
                if (foundIndex !== -1) {
                    currentProperties.splice(foundIndex, 1);
                }
            });

            return currentProperties;
        }

        return self;
    };

    var CaseProperty = function (name, propertyManager) {
        var self = {};
        self.name = ko.observable();
        let prevValue = '';
        self.name.subscribe(function (newValue) {
            if (!newValue) {
                return;
            }

            propertyManager.updatePropertyValue(newValue, prevValue);
            prevValue = newValue;
        });
        self.name(name);
        return self;
    };

    var CaseDedupe = function (
        initialName,
        initialCaseType,
        caseTypeOptions,
        initialMatchType,
        initialCaseProperties,
        initialIncludeClosed,
        initialPropertiesToUpdate,
        allCaseProperties
    ) {
        var self = {};
        self.name = ko.observable(initialName);
        self.caseType = ko.observable();
        self.caseProperties = ko.observableArray();
        self.includeClosed = ko.observable(initialIncludeClosed);
        self.propertyManager = PropertyManager(self.caseType, self.caseProperties, allCaseProperties);

        // Create a separate property for this so that outside callers do not need
        // to be aware of this class's structure. Also functions as making the variable read-only
        self.availablePropertyMap = ko.pureComputed(function () {
            return self.propertyManager.availablePropertyMap();
        });

        self.caseType(initialCaseType);

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

        self.caseProperties(_.map(initialCaseProperties, function (name) {
            return CaseProperty(name, self.propertyManager);
        }));
        self.removeCaseProperty = function (item) {
            self.propertyManager.removeProperty(item);
        };
        self.addCaseProperty = function () {
            self.propertyManager.addProperty(CaseProperty('', self.propertyManager));
        };

        if (self.caseProperties().length === 0) {
            self.addCaseProperty();
        }
        self.serializedCaseProperties = ko.computed(function () {
            return ko.toJSON(self.caseProperties);
        });

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
        casePropertyInput.register();

        // This is a little hacky; it prevents the "multiple bindings to same
        // element" error.
        var caseFilterElement = $("#caseFiltersForm");
        caseFilterElement.detach();

        var caseDedupe = CaseDedupe(
            initialPageData.get('name'),
            initialPageData.get('case_type'),
            initialPageData.get('case_types'),
            initialPageData.get('match_type'),
            initialPageData.get('case_properties'),
            initialPageData.get('include_closed'),
            initialPageData.get('properties_to_update'),
            initialPageData.get("all_case_properties")
        );
        $("#case-dedupe-rule-definition").koApplyBindings(caseDedupe);

        $("#caseFilters").append(caseFilterElement);

        $('#rule-criteria-panel').koApplyBindings(CaseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants'),
            caseDedupe.caseType
        ));
    });
});

