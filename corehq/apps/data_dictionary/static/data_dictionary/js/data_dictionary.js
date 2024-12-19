'use strict';
hqDefine("data_dictionary/js/data_dictionary", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/main",
    "analytix/js/google",
    "hqwebapp/js/ui_elements/bootstrap3/ui-element-key-val-list",
    "DOMPurify/dist/purify.min",
    "hqwebapp/js/toggles",
    "hqwebapp/js/bootstrap3/knockout_bindings.ko",
    "data_interfaces/js/make_read_only",
    'hqwebapp/js/select2_knockout_bindings.ko',
    'knockout-sortable/build/knockout-sortable',
    "commcarehq",
], function (
    $,
    ko,
    _,
    initialPageData,
    hqMain,
    googleAnalytics,
    uiElementKeyValueList,
    DOMPurify,
    toggles
) {
    var caseType = function (
        name,
        fhirResourceType,
        deprecated,
        moduleCount,
        geoCaseProp,
        isSafeToDelete,
        changeSaveButton,
        resetSaveButton,
        dataUrl
    ) {
        var self = {};
        self.name = name || gettext("No Name");
        self.deprecated = deprecated;
        self.appCount = moduleCount;  // The number of application modules using this case type
        self.url = "#" + name;
        self.fhirResourceType = ko.observable(fhirResourceType);
        self.groups = ko.observableArray();
        self.geoCaseProp = geoCaseProp;
        self.canDelete = isSafeToDelete;
        self.changeSaveButton = changeSaveButton;
        self.resetSaveButton = resetSaveButton;
        self.dataUrl = dataUrl;

        self.groups.subscribe(changeSaveButton);

        self.fetchCaseProperties = function () {
            if (self.groups().length === 0) {
                let caseTypeUrl = self.dataUrl + self.name + '/';
                recurseChunks(caseTypeUrl);
            }
        };

        const recurseChunks = function (nextUrl) {
            $.getJSON(nextUrl, function (data) {
                setCaseProperties(data.groups);
                self.resetSaveButton();
                nextUrl = data._links.next;
                if (nextUrl) {
                    recurseChunks(nextUrl);
                }
            });
        };

        const setCaseProperties = function (groupData) {
            for (let group of groupData) {
                let groupObj = _.find(self.groups(), function (g) {
                    return g.id === group.id;
                });
                if (!groupObj) {
                    groupObj = groupsViewModel(
                        self.name,
                        group.id,
                        group.name,
                        group.description,
                        group.deprecated,
                        self.changeSaveButton
                    );
                    self.groups.push(groupObj);
                }

                for (let prop of group.properties) {
                    const isGeoCaseProp = (self.geoCaseProp === prop.name && prop.data_type === 'gps');
                    if (self.canDelete && !prop.is_safe_to_delete) {
                        self.canDelete = false;
                    }

                    var propObj = propertyListItem(
                        prop,
                        false,
                        group.name,
                        self.name,
                        isGeoCaseProp,
                        groupObj.name(),
                        self.changeSaveButton
                    );
                    groupObj.properties.push(propObj);
                }
            }
        };

        return self;
    };

    var groupsViewModel = function (
        caseType,
        id,
        name,
        description,
        deprecated,
        changeSaveButton
    ) {
        var self = {};
        self.id = id;
        self.name = ko.observable(name);
        self.description = ko.observable(description);
        self.caseType = caseType;
        self.properties = ko.observableArray();
        self.newPropertyName = ko.observable();
        self.expanded = ko.observable(true);
        self.toggleExpanded = () => self.expanded(!self.expanded());
        self.deprecated = deprecated;
        // Ensures that groups are not directly hidden on clicking the deprecated button
        self.toBeDeprecated = ko.observable(deprecated || false);
        self.deprecateGroup = function () {
            self.toBeDeprecated(true);
        };

        self.restoreGroup = function () {
            self.toBeDeprecated(false);
        };
        // Show a warning that properties will be transferred to "No Group" section on deprecating a group.
        self.showGroupPropertyTransferWarning = ko.computed(function () {
            return self.toBeDeprecated() && !deprecated && self.properties().length > 0;
        });

        self.newCaseProperty = function () {
            if (self.newPropertyName().trim()) {
                const prop = {
                    'name': self.newPropertyName(),
                    'label': self.newPropertyName(),
                    'allowedValues': {},
                };
                let propObj = propertyListItem(
                    prop,
                    false,
                    self.name(),
                    self.caseType,
                    false,
                    self.name(),
                    changeSaveButton
                );
                self.newPropertyName(undefined);
                self.properties.push(propObj);
            }
        };

        self.name.subscribe(changeSaveButton);
        self.description.subscribe(changeSaveButton);
        self.toBeDeprecated.subscribe(changeSaveButton);
        self.properties.subscribe(changeSaveButton);

        return self;
    };

    var propertyListItem = function (
        prop,
        isGroup,
        groupName,
        caseType,
        isGeoCaseProp,
        loadedGroup,
        changeSaveButton
    ) {
        var self = {};
        self.id = prop.id;
        self.name = prop.name;
        self.label = ko.observable(prop.label);
        self.expanded = ko.observable(true);
        self.isGroup = isGroup;
        self.group = ko.observable(groupName);
        self.caseType = caseType;
        self.dataType = ko.observable(prop.data_type);
        self.description = ko.observable(prop.description);
        self.fhirResourcePropPath = ko.observable(prop.fhir_resource_prop_path);
        self.originalResourcePropPath = prop.fhir_resource_prop_path;
        self.deprecated = ko.observable(prop.deprecated || false);
        self.isGeoCaseProp = ko.observable(isGeoCaseProp);
        self.isSafeToDelete = ko.observable(prop.is_safe_to_delete);
        self.deleted = ko.observable(false);
        self.hasChanges = false;
        self.index = prop.index;
        self.loadedGroup = loadedGroup;  // The group this case property is part of when page was loaded. Used to identify group changes

        self.trackObservableChange = function (observable) {
            // Keep track of old val for observable, and subscribe to new changes.
            // We can then identify when the val has changed.
            let oldVal = observable();
            observable.subscribe(function (newVal) {
                if (!newVal && !oldVal) {
                    return;
                }
                if (newVal !== oldVal) {
                    self.hasChanges = true;
                }
                oldVal = newVal;
            });
        };

        self.allowedValuesChanged = function () {
            // Default to true on any change callback as this is how it is
            // done for the save button
            self.hasChanges = true;
        };

        self.removeFHIRResourcePropertyPath = ko.observable(prop.removeFHIRResourcePropertyPath || false);
        let subTitle;
        if (toggles.toggleEnabled("CASE_IMPORT_DATA_DICTIONARY_VALIDATION")) {
            subTitle = gettext("When importing data, CommCare will not save a row if its cells don't match these valid values.");
        } else {
            subTitle = gettext("Help colleagues upload correct data into case properties by listing the valid values here.");
        }
        self.allowedValues = uiElementKeyValueList.new(
            String(Math.random()).slice(2), /* guid */
            interpolate('Edit valid values for "%s"', [name]), /* modalTitle */
            subTitle, /* subTitle */
            {"key": gettext("valid value"), "value": gettext("description")}, /* placeholders */
            10 /* maxDisplay */
        );
        self.allowedValues.val(prop.allowed_values);
        if (initialPageData.get('read_only_mode')) {
            self.allowedValues.setEdit(false);
        }
        self.$allowedValues = self.allowedValues.ui;

        self.toggle = function () {
            self.expanded(!self.expanded());
        };

        self.deprecateProperty = function () {
            if (toggles.toggleEnabled('MICROPLANNING') && self.isGeoCaseProp()) {
                self.confirmGeospatialDeprecation();
            } else {
                self.deprecated(true);
            }
        };

        self.confirmGeospatialDeprecation = function () {
            const $modal = $("#deprecate-geospatial-prop-modal").modal('show');
            $("#deprecate-geospatial-prop-btn").off('click').on('click', function () {
                self.deprecated(true);
                $modal.modal('hide');
            });
        };

        self.restoreProperty = function () {
            self.deprecated(false);
        };

        self.removePath = function () {
            self.removeFHIRResourcePropertyPath(true);
            // set back to original to delete the corresponding entry on save
            self.fhirResourcePropPath(self.originalResourcePropPath);
        };

        self.restorePath = function () {
            self.removeFHIRResourcePropertyPath(false);
        };

        self.canHaveAllowedValues = ko.computed(function () {
            return self.dataType() === 'select';
        });

        self.confirmDeleteProperty = function () {
            const $modal = $("#delete-case-prop-modal").modal('show');
            $("#delete-case-prop-name").text(self.name);
            $("#delete-case-prop-btn").off("click").on("click", () => {
                self.deleted(true);
                $modal.modal('hide');
            });
        };

        subscribePropObservable(self.description);
        subscribePropObservable(self.label);
        subscribePropObservable(self.fhirResourcePropPath);
        subscribePropObservable(self.dataType);
        subscribePropObservable(self.deprecated);
        subscribePropObservable(self.deleted);
        subscribePropObservable(self.removeFHIRResourcePropertyPath);
        self.allowedValues.on('change', changeSaveButton);
        self.allowedValues.on('change', self.allowedValuesChanged);

        function subscribePropObservable(prop) {
            prop.subscribe(changeSaveButton);
            self.trackObservableChange(prop);
        }

        return self;
    };

    var dataDictionaryModel = function (dataUrl, casePropertyUrl, typeChoices, fhirResourceTypes) {
        var self = {};
        self.caseTypes = ko.observableArray();
        self.activeCaseType = ko.observable();
        self.fhirResourceType = ko.observable();
        self.removefhirResourceType = ko.observable(false);
        self.newPropertyName = ko.observable();
        self.newGroupName = ko.observable();
        self.showAll = ko.observable(false);
        self.availableDataTypes = typeChoices;
        self.fhirResourceTypes = ko.observableArray(fhirResourceTypes);

        const params = new URLSearchParams(document.location.search);
        self.showDeprecatedCaseTypes = ko.observable(params.get("load_deprecated_case_types") !== null);

        // Elements with this class have a hidden class to hide them on page load. If we don't do this, then the elements
        // will flash on the page for a bit while the KO bindings are being applied.
        $(".deprecate-case-type").removeClass('hidden');

        self.saveButton = hqMain.initSaveButton({
            unsavedMessage: gettext("You have unsaved changes to your data dictionary."),
            save: function () {
                const groups = [];
                const properties = [];
                _.each(self.activeCaseTypeData(), function (group, index) {
                    if (group.name() !== "") {
                        let groupData = {
                            'caseType': group.caseType,
                            'id': group.id,
                            'name': group.name(),
                            'description': group.description(),
                            'index': index,
                            'deprecated': group.toBeDeprecated(),
                        };
                        groups.push(groupData);
                    }

                    _.each(group.properties(), function (element, index) {
                        if (element.deleted() && !element.id) {
                            return;
                        }
                        const propIndex = group.toBeDeprecated() ? 0 : index;
                        const propGroup = group.toBeDeprecated() ? "" : group.name();
                        if (!element.hasChanges
                            && propIndex === element.index
                            && element.loadedGroup === propGroup) {
                            return;
                        }

                        const allowedValues = element.allowedValues.val();
                        let pureAllowedValues = {};
                        for (const key in allowedValues) {
                            pureAllowedValues[DOMPurify.sanitize(key)] = DOMPurify.sanitize(allowedValues[key]);
                        }
                        var data = {
                            'caseType': element.caseType,
                            'name': element.name,
                            'label': element.label() || element.name,
                            'index': propIndex,
                            'data_type': element.dataType(),
                            'group': propGroup,
                            'description': element.description(),
                            'fhir_resource_prop_path': (
                                element.fhirResourcePropPath() ? element.fhirResourcePropPath().trim() : element.fhirResourcePropPath()),
                            'deprecated': element.deprecated(),
                            'deleted': element.deleted(),
                            'removeFHIRResourcePropertyPath': element.removeFHIRResourcePropertyPath(),
                            'allowed_values': pureAllowedValues,
                        };
                        properties.push(data);
                    });
                });
                self.saveButton.ajax({
                    url: casePropertyUrl,
                    type: 'POST',
                    dataType: 'JSON',
                    data: {
                        'groups': JSON.stringify(groups),
                        'properties': JSON.stringify(properties),
                        'fhir_resource_type': self.fhirResourceType(),
                        'remove_fhir_resource_type': self.removefhirResourceType(),
                        'case_type': self.activeCaseType(),
                    },
                    success: function () {
                        window.location.reload();
                    },
                    // Error handling is managed by SaveButton logic in main.js
                });
            },
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        const resetSaveButton = function () {
            self.saveButton.setState('saved');
        };

        self.init = function (callback) {
            // Get list of case types
            $.getJSON(dataUrl, {load_deprecated_case_types: self.showDeprecatedCaseTypes()})
                .done(function (data) {
                    _.each(data.case_types, function (caseTypeData) {
                        var caseTypeObj = caseType(
                            caseTypeData.name,
                            caseTypeData.fhir_resource_type,
                            caseTypeData.is_deprecated,
                            caseTypeData.module_count,
                            data.geo_case_property,
                            caseTypeData.is_safe_to_delete,
                            changeSaveButton,
                            resetSaveButton,
                            dataUrl
                        );
                        self.caseTypes.push(caseTypeObj);
                    });
                    if (
                        self.caseTypes().length
                        // Check that hash navigation has not already loaded the first case type
                        && self.caseTypes()[0] !== self.getHashNavigationCaseType()
                    ) {
                        // `self.goToCaseType()` calls `caseType.fetchCaseProperties()`
                        // to fetch the case properties of the first case type
                        let caseType = self.caseTypes()[0];
                        self.goToCaseType(caseType);
                    }
                    self.fhirResourceType.subscribe(changeSaveButton);
                    self.removefhirResourceType.subscribe(changeSaveButton);
                    callback();
                });
        };

        self.getHashNavigationCaseType = function () {
            let fullHash = window.location.hash.split('?')[0],
                hash = fullHash.substring(1);
            return _.find(self.caseTypes(), function (prop) {
                return prop.name === hash;
            });
        };

        self.getActiveCaseType = function () {
            return _.find(self.caseTypes(), function (prop) {
                return prop.name === self.activeCaseType();
            });
        };

        self.getCaseTypeGroupsObservable = function () {
            let caseType = self.getActiveCaseType();
            if (caseType) {
                return caseType.groups;  // The observable, not its value
            }
        };

        self.activeCaseTypeData = function () {
            const groupsObs = self.getCaseTypeGroupsObservable();
            return (groupsObs) ? groupsObs() : [];
        };

        self.isActiveCaseTypeDeprecated = function () {
            const activeCaseType = self.getActiveCaseType();
            return (activeCaseType) ? activeCaseType.deprecated : false;
        };

        self.canDeleteActiveCaseType = function () {
            const activeCaseType = self.getActiveCaseType();
            return (activeCaseType) ? activeCaseType.canDelete : false;
        };

        self.activeCaseTypeModuleCount = function () {
            const activeCaseType = self.getActiveCaseType();
            return (activeCaseType) ? activeCaseType.appCount : 0;
        };

        self.deprecateCaseType = function () {
            self.deprecateOrRestoreCaseType(true);
        };

        self.restoreCaseType = function () {
            self.deprecateOrRestoreCaseType(false);
        };

        self.deprecateOrRestoreCaseType = function (shouldDeprecate) {
            let activeCaseType = self.getActiveCaseType();
            if (!activeCaseType) {
                return;
            }

            activeCaseType.deprecated = shouldDeprecate;
            $("#case-type-error").hide();
            $.ajax({
                url: initialPageData.reverse('deprecate_or_restore_case_type', activeCaseType.name),
                method: 'POST',
                data: {
                    'is_deprecated': shouldDeprecate,
                },
                success: function () {
                    window.location.reload(true);
                },
                error: function () {
                    $("#case-type-error").show();
                },
            });
        };

        self.deleteCaseType = function () {
            $("#case-type-error").hide();
            $.ajax({
                url: initialPageData.reverse('delete_case_type', self.getActiveCaseType().name),
                method: 'POST',
                success: function () {
                    window.location.href = initialPageData.reverse('data_dictionary');
                },
                error: function () {
                    $("#case-type-error").show();
                },
            });
        };

        self.goToCaseType = function (caseType) {
            if (self.saveButton.state === 'save') {
                var dialog = confirm(gettext('You have unsaved changes to this case type. Are you sure you would like to continue?'));
                if (!dialog) {
                    return;
                }
            }
            caseType.fetchCaseProperties();
            self.activeCaseType(caseType.name);
            self.fhirResourceType(caseType.fhirResourceType());
            self.removefhirResourceType(false);
            self.saveButton.setState('saved');
        };

        function isNameValid(nameStr) {
            // First character must be a letter, and the entire name can only contain letters, numbers, '-', and '_'
            const pattern = /^[a-zA-Z][a-zA-Z0-9-_]*$/;
            return pattern.test(nameStr);
        }

        self.newPropertyNameValid = function (name) {
            if (!name) {
                return true;
            }
            return isNameValid(name);
        };

        self.newPropertyNameUnique = function (name) {
            if (!name) {
                return true;
            }

            const propertyNameFormatted = name.toLowerCase().trim();
            const activeCaseTypeData = self.activeCaseTypeData();
            for (const group of activeCaseTypeData) {
                if (group.properties().find(v => v.name.toLowerCase() === propertyNameFormatted)) {
                    return false;
                }
            }
            return true;
        };

        self.newGroupNameValid = ko.computed(function () {
            if (!self.newGroupName()) {
                return true;
            }
            return isNameValid(self.newGroupName());
        });

        self.newGroupNameUnique = ko.computed(function () {
            if (!self.newGroupName()) {
                return true;
            }

            const groupNameFormatted = self.newGroupName().toLowerCase().trim();
            const activeCaseTypeData = self.activeCaseTypeData();
            for (const group of activeCaseTypeData) {
                if (group.name().toLowerCase() === groupNameFormatted) {
                    return false;
                }
            }
            return true;
        });

        self.newGroup = function () {
            if (_.isString(self.newGroupName()) && self.newGroupName().trim()) {
                var group = groupsViewModel(
                    self.activeCaseType(),
                    null,
                    self.newGroupName(),
                    '',
                    false,
                    changeSaveButton
                );
                let groupsObs = self.getCaseTypeGroupsObservable();
                groupsObs.push(group);  // TODO: Broken for computed value
                self.newGroupName(undefined);
            }
        };

        self.toggleGroup = function (group) {
            group.toggle();
            var groupIndex = _.findIndex(self.casePropertyList(), function (element) {
                return element.name === group.name;
            });
            var i = groupIndex + 1;
            var next = self.casePropertyList()[i];
            while (next && !next.isGroup) {
                next.toggle();
                i++;
                next = self.casePropertyList()[i];
            }
        };

        self.showDeprecated = function () {
            self.showAll(true);
        };

        self.hideDeprecated = function () {
            self.showAll(false);
        };

        self.removeResourceType = function () {
            self.removefhirResourceType(true);
        };

        self.restoreResourceType = function () {
            self.removefhirResourceType(false);
        };

        self.toggleShowDeprecatedCaseTypes = function () {
            self.showDeprecatedCaseTypes(!self.showDeprecatedCaseTypes());
            const pageUrl = new URL(window.location.href);
            if (self.showDeprecatedCaseTypes()) {
                pageUrl.searchParams.append('load_deprecated_case_types', true);
            } else {
                pageUrl.searchParams.delete('load_deprecated_case_types');
            }
            window.location.href = pageUrl;
        };

        // CREATE workflow
        self.name = ko.observable("").extend({
            rateLimit: { method: "notifyWhenChangesStop", timeout: 400 },
        });

        self.nameValid = ko.observable(false);
        self.nameUnique = ko.observable(false);
        self.nameChecked = ko.observable(false);
        self.name.subscribe((value) => {
            if (!value) {
                self.nameChecked(false);
                return;
            }
            let existing = _.find(self.caseTypes(), function (prop) {
                return prop.name === value;
            });
            self.nameUnique(!existing);
            self.nameValid(isNameValid(self.name()));
            self.nameChecked(true);
        });

        self.formCreateCaseTypeSent = ko.observable(false);
        self.submitCreate = function () {
            self.formCreateCaseTypeSent(true);
            return true;
        };

        self.clearForm = function () {
            $("#create-case-type-form").trigger("reset");
            self.name("");
            self.nameValid(false);
            self.nameUnique(false);
            self.nameChecked(false);
            return true;
        };

        $(document).on('hide.bs.modal',  () => {
            return self.clearForm();
        });

        return self;
    };

    $(function () {
        var dataUrl = initialPageData.reverse('data_dictionary_json_case_types'),
            casePropertyUrl = initialPageData.reverse('update_case_property'),
            typeChoices = initialPageData.get('typeChoices'),
            fhirResourceTypes = initialPageData.get('fhirResourceTypes'),
            viewModel = dataDictionaryModel(dataUrl, casePropertyUrl, typeChoices, fhirResourceTypes);

        function doHashNavigation() {
            let caseType = viewModel.getHashNavigationCaseType();
            if (caseType) {
                viewModel.goToCaseType(caseType);
            }
        }

        window.onhashchange = doHashNavigation;

        viewModel.init(doHashNavigation);
        $('#hq-content').parent().koApplyBindings(viewModel);
        $('#download-dict').click(function () {
            googleAnalytics.track.event('Data Dictionary', 'downloaded data dictionary');
        });

    });
});
