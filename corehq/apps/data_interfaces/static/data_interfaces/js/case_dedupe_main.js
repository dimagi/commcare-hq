hqDefine("data_interfaces/js/case_dedupe_main", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_property_input',
    'data_interfaces/js/case_rule_criteria',
    'hqwebapp/js/bootstrap3/widgets',
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
    caseType is expected to be an observable.
    selectedProperties is expected to be an observableArray.
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

        self.updatePropertyValue = function (newValue, oldValue) {
            let currentProperties = self.availablePropertyMap()[self.caseType()];
            currentProperties = reserveProperties([newValue], currentProperties);
            currentProperties = restoreProperty(oldValue, currentProperties);

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
            // make the specified propertyNames unavailable for future selection
            return _.difference(currentProperties, propertyNames);
        }

        return self;
    };

    const CaseProperty = function (name, propertyManager) {
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

    const PropertyToUpdate = function (name, valueType, value, propertyManager) {
        var self = {};
        self.name = ko.observable();
        self.valueType = ko.observable(valueType);
        self.value = ko.observable(value);

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

    const CaseDedupe = function (
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
        self.caseType = ko.observable(initialCaseType);
        self.includeClosed = ko.observable(initialIncludeClosed);
        self.caseTypeOptions = caseTypeOptions;
        self.matchType = ko.observable(initialMatchType);
        self.matchTypeText = ko.computed(function () {
            return (self.matchType() === 'ANY') ? gettext('OR') : gettext('AND');
        });
        self.matchTypeOptions = ['ALL', 'ANY'];
        self.matchTypeOptionsText = function (item) {
            if (item === 'ANY') {
                return gettext('True when ANY of the case properties match');
            }
            return gettext('True when ALL of the case properties match');
        };

        /* Case Properties */
        self.caseProperties = ko.observableArray();
        self.propertyManager = PropertyManager(self.caseType, self.caseProperties, allCaseProperties);
        // Create a separate property for this so that outside callers do not need
        // to be aware of this class's structure. Also functions as making the variable read-only
        self.availablePropertyMap = ko.pureComputed(function () {
            return self.propertyManager.availablePropertyMap();
        });

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
        /* End Case Properties */

        /* Update Actions */
        self.propertiesToUpdate = ko.observableArray();
        self.actionManager = PropertyManager(self.caseType, self.propertiesToUpdate, allCaseProperties);
        self.availableActionPropertyMap = ko.pureComputed(function () {
            return self.actionManager.availablePropertyMap();
        });
        self.propertiesToUpdate(_.map(initialPropertiesToUpdate, function (property) {
            return PropertyToUpdate(property.name, property.valueType, property.value, self.actionManager);
        }));
        self.removePropertyToUpdate = function (item) {
            self.actionManager.removeProperty(item);
        };
        self.addPropertyToUpdate = function () {
            self.actionManager.addProperty(PropertyToUpdate('', 'EXACT', '', self.actionManager));
        };
        self.serializedPropertiesToUpdate = ko.computed(function () {
            return ko.toJSON(self.propertiesToUpdate);
        });
        /* End Update Actions */

        return self;
    };

    $(function () {
        casePropertyInput.register();

        // This is a little hacky; it prevents the "multiple bindings to same
        // element" error.
        const caseFilterElement = $("#caseFiltersForm");
        caseFilterElement.detach();

        const caseDedupe = CaseDedupe(
            initialPageData.get('name'),
            initialPageData.get('case_type'),
            initialPageData.get('case_types'),
            initialPageData.get('match_type'),
            initialPageData.get('case_properties'),
            initialPageData.get('include_closed'),
            initialPageData.get('properties_to_update'),
            initialPageData.get('all_case_properties')
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

