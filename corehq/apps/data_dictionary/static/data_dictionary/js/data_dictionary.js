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
    var caseType = function (name, fhirResourceType, deprecated, moduleCount, geoCaseProp, isSafeToDelete) {
        var self = {};
        self.name = name || gettext("No Name");
        self.deprecated = deprecated;
        self.appCount = moduleCount;  // The number of application modules using this case type
        self.url = "#" + name;
        self.fhirResourceType = ko.observable(fhirResourceType);
        self.groups = ko.observableArray();
        self.geoCaseProp = geoCaseProp;
        self.canDelete = isSafeToDelete;

        self.init = function (groupData, changeSaveButton) {
            for (let group of groupData) {
                let groupObj = groupsViewModel(self.name, group.id, group.name, group.description, group.deprecated);
                groupObj.name.subscribe(changeSaveButton);
                groupObj.description.subscribe(changeSaveButton);
                groupObj.toBeDeprecated.subscribe(changeSaveButton);

                for (let prop of group.properties) {
                    const isGeoCaseProp = (self.geoCaseProp === prop.name && prop.data_type === 'gps');
                    if (self.canDelete && !prop.is_safe_to_delete) {
                        self.canDelete = false;
                    }

                    var propObj = propertyListItem(prop.name, prop.label, false, group.name, self.name, prop.data_type,
                        prop.description, prop.allowed_values, prop.fhir_resource_prop_path, prop.deprecated,
                        prop.removeFHIRResourcePropertyPath, isGeoCaseProp, prop.is_safe_to_delete, prop.id);
                    propObj.description.subscribe(changeSaveButton);
                    propObj.label.subscribe(changeSaveButton);
                    propObj.fhirResourcePropPath.subscribe(changeSaveButton);
                    propObj.dataType.subscribe(changeSaveButton);
                    propObj.deprecated.subscribe(changeSaveButton);
                    propObj.deleted.subscribe(changeSaveButton);
                    propObj.removeFHIRResourcePropertyPath.subscribe(changeSaveButton);
                    propObj.allowedValues.on('change', changeSaveButton);
                    groupObj.properties.push(propObj);
                }
                groupObj.properties.subscribe(changeSaveButton);
                self.groups.push(groupObj);
            }
        };

        return self;
    };

    var groupsViewModel = function (caseType, id, name, description, deprecated) {
        var self = {};
        self.id = id;
        self.name = ko.observable(name);
        self.description = ko.observable(description);
        self.caseType = caseType;
        self.properties = ko.observableArray();
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
        return self;
    };

    var propertyListItem = function (name, label, isGroup, groupName, caseType, dataType, description, allowedValues,
        fhirResourcePropPath, deprecated, removeFHIRResourcePropertyPath, isGeoCaseProp, isSafeToDelete, id) {
        var self = {};
        self.id = id;
        self.name = name;
        self.label = ko.observable(label);
        self.expanded = ko.observable(true);
        self.isGroup = isGroup;
        self.group = ko.observable(groupName);
        self.caseType = caseType;
        self.dataType = ko.observable(dataType);
        self.description = ko.observable(description);
        self.fhirResourcePropPath = ko.observable(fhirResourcePropPath);
        self.originalResourcePropPath = fhirResourcePropPath;
        self.deprecated = ko.observable(deprecated || false);
        self.isGeoCaseProp = ko.observable(isGeoCaseProp);
        self.isSafeToDelete = ko.observable(isSafeToDelete);
        self.deleted = ko.observable(false);
        self.removeFHIRResourcePropertyPath = ko.observable(removeFHIRResourcePropertyPath || false);
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
        self.allowedValues.val(allowedValues);
        if (initialPageData.get('read_only_mode')) {
            self.allowedValues.setEdit(false);
        }
        self.$allowedValues = self.allowedValues.ui;

        self.toggle = function () {
            self.expanded(!self.expanded());
        };

        self.deprecateProperty = function () {
            if (toggles.toggleEnabled('GEOSPATIAL') && self.isGeoCaseProp()) {
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
        self.caseGroupList = ko.observableArray();
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
                _.each(self.caseGroupList(), function (group, index) {
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

                        const allowedValues = element.allowedValues.val();
                        let pureAllowedValues = {};
                        for (const key in allowedValues) {
                            pureAllowedValues[DOMPurify.sanitize(key)] = DOMPurify.sanitize(allowedValues[key]);
                        }
                        var data = {
                            'caseType': element.caseType,
                            'name': element.name,
                            'label': element.label() || element.name,
                            'index': index,
                            'data_type': element.dataType(),
                            'group': group.toBeDeprecated() ? "" : group.name(),
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

        self.init = function (callback) {
            $.getJSON(dataUrl, {load_deprecated_case_types: self.showDeprecatedCaseTypes()})
                .done(function (data) {
                    _.each(data.case_types, function (caseTypeData) {
                        var caseTypeObj = caseType(
                            caseTypeData.name,
                            caseTypeData.fhir_resource_type,
                            caseTypeData.is_deprecated,
                            caseTypeData.module_count,
                            data.geo_case_property,
                            caseTypeData.is_safe_to_delete
                        );
                        caseTypeObj.init(caseTypeData.groups, changeSaveButton);
                        self.caseTypes.push(caseTypeObj);
                    });
                    if (self.caseTypes().length) {
                        self.goToCaseType(self.caseTypes()[0]);
                    }
                    self.caseGroupList.subscribe(changeSaveButton);
                    self.fhirResourceType.subscribe(changeSaveButton);
                    self.removefhirResourceType.subscribe(changeSaveButton);
                    callback();
                });
        };

        self.getActiveCaseType = function () {
            return _.find(self.caseTypes(), function (prop) {
                return prop.name === self.activeCaseType();
            });
        };

        self.activeCaseTypeData = function () {
            var caseTypes = self.caseTypes();
            if (caseTypes.length) {
                var caseType = self.getActiveCaseType();
                if (caseType) {
                    return caseType.groups();
                }
            }
            return [];
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
            self.activeCaseType(caseType.name);
            self.fhirResourceType(caseType.fhirResourceType());
            self.removefhirResourceType(false);
            self.caseGroupList(self.activeCaseTypeData());
            self.saveButton.setState('saved');
        };

        function isNameValid(nameStr) {
            // First character must be a letter, and the entire name can only contain letters, numbers, '-', and '_'
            const pattern = /^[a-zA-Z][a-zA-Z0-9-_]*$/;
            return pattern.test(nameStr);
        }

        self.newPropertyNameValid = ko.computed(function () {
            if (!self.newPropertyName()) {
                return true;
            }
            return isNameValid(self.newPropertyName());
        });

        self.newPropertyNameUnique = ko.computed(function () {
            if (!self.newPropertyName()) {
                return true;
            }

            const propertyNameFormatted = self.newPropertyName().toLowerCase().trim();
            const activeCaseTypeData = self.activeCaseTypeData();
            for (const group of activeCaseTypeData) {
                if (group.properties().find(v => v.name.toLowerCase() === propertyNameFormatted)) {
                    return false;
                }
            }
            return true;
        });

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

        self.newCaseProperty = function () {
            if (_.isString(self.newPropertyName()) && self.newPropertyName().trim()) {
                let lastGroup = self.caseGroupList()[self.caseGroupList().length - 1];
                var prop = propertyListItem(self.newPropertyName(), self.newPropertyName(), false, lastGroup.name(), self.activeCaseType(), '', '', {});
                prop.dataType.subscribe(changeSaveButton);
                prop.description.subscribe(changeSaveButton);
                prop.label.subscribe(changeSaveButton);
                prop.fhirResourcePropPath.subscribe(changeSaveButton);
                prop.deprecated.subscribe(changeSaveButton);
                prop.removeFHIRResourcePropertyPath.subscribe(changeSaveButton);
                prop.allowedValues.on('change', changeSaveButton);
                self.newPropertyName(undefined);
                lastGroup.properties.push(prop);
            }
        };

        self.newGroup = function () {
            if (_.isString(self.newGroupName()) && self.newGroupName().trim()) {
                var group = groupsViewModel(self.activeCaseType(), null, self.newGroupName(), '', false);
                self.caseGroupList.push(group);
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
        var dataUrl = initialPageData.reverse('data_dictionary_json'),
            casePropertyUrl = initialPageData.reverse('update_case_property'),
            typeChoices = initialPageData.get('typeChoices'),
            fhirResourceTypes = initialPageData.get('fhirResourceTypes'),
            viewModel = dataDictionaryModel(dataUrl, casePropertyUrl, typeChoices, fhirResourceTypes);

        function doHashNavigation() {
            let fullHash = window.location.hash.split('?')[0],
                hash = fullHash.substring(1);
            let caseType = _.find(viewModel.caseTypes(), function (prop) {
                return prop.name === hash;
            });
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
