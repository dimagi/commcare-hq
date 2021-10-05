hqDefine("data_dictionary/js/data_dictionary", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/main",
    "analytix/js/google",
    "hqwebapp/js/ui_elements/ui-element-key-val-list",
    "hqwebapp/js/knockout_bindings.ko",
], function (
    $,
    ko,
    _,
    initialPageData,
    hqMain,
    googleAnalytics,
    uiElementKeyValueList
) {
    var caseType = function (name, fhirResourceType) {
        var self = {};
        self.name = name || gettext("No Name");
        self.url = "#" + name;
        self.fhirResourceType = ko.observable(fhirResourceType);
        self.properties = ko.observableArray();

        self.init = function (groupDict, changeSaveButton) {
            _.each(groupDict, function (properties, group) {
                var groupObj = propertyListItem(group, true, group, self.name);
                self.properties.push(groupObj);
                _.each(properties, function (prop) {
                    var propObj = propertyListItem(prop.name, false, prop.group, self.name, prop.data_type,
                        prop.description, prop.allowed_values, prop.fhir_resource_prop_path, prop.deprecated,
                        prop.removeFHIRResourcePropertyPath);
                    propObj.description.subscribe(changeSaveButton);
                    propObj.fhirResourcePropPath.subscribe(changeSaveButton);
                    propObj.dataType.subscribe(changeSaveButton);
                    propObj.deprecated.subscribe(changeSaveButton);
                    propObj.removeFHIRResourcePropertyPath.subscribe(changeSaveButton);
                    propObj.allowedValues.on('change', changeSaveButton);
                    self.properties.push(propObj);
                });
            });
        };

        return self;
    };

    var propertyListItem = function (name, isGroup, groupName, caseType, dataType, description, allowedValues,
        fhirResourcePropPath, deprecated, removeFHIRResourcePropertyPath) {
        var self = {};
        self.name = name;
        self.expanded = ko.observable(true);
        self.isGroup = isGroup;
        self.group = ko.observable(groupName);
        self.caseType = caseType;
        self.dataType = ko.observable(dataType);
        self.description = ko.observable(description);
        self.fhirResourcePropPath = ko.observable(fhirResourcePropPath);
        self.originalResourcePropPath = fhirResourcePropPath;
        self.deprecated = ko.observable(deprecated || false);
        self.removeFHIRResourcePropertyPath = ko.observable(removeFHIRResourcePropertyPath || false);
        self.allowedValues = uiElementKeyValueList.new(
            String(Math.random()).slice(2), /* guid */
            interpolate('Edit valid values for "%s"', [name]), /* modalTitle */
            gettext("When importing case data, CommCare will warn if rows don't match valid values"), /* subTitle */
            {"key": gettext("valid value"), "value": gettext("description")}, /* placeholders */
            10 /* maxDisplay */
        );
        self.allowedValues.val(allowedValues);
        self.$allowedValues = self.allowedValues.ui;

        self.toggle = function () {
            self.expanded(!self.expanded());
        };

        self.deprecateProperty = function () {
            self.deprecated(true);
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
        self.casePropertyList = ko.observableArray();
        self.showAll = ko.observable(false);
        self.availableDataTypes = typeChoices;
        self.fhirResourceTypes = ko.observableArray(fhirResourceTypes);
        self.saveButton = hqMain.initSaveButton({
            unsavedMessage: gettext("You have unsaved changes to your data dictionary."),
            save: function () {
                var postProperties = [];
                var currentGroup = '';
                _.each(self.casePropertyList(), function (element) {
                    if (!element.isGroup) {
                        var data = {
                            'caseType': element.caseType,
                            'name': element.name,
                            'data_type': element.dataType(),
                            'group': currentGroup,
                            'description': element.description(),
                            'fhir_resource_prop_path': (
                                element.fhirResourcePropPath() ? element.fhirResourcePropPath().trim() : element.fhirResourcePropPath()),
                            'deprecated': element.deprecated(),
                            'removeFHIRResourcePropertyPath': element.removeFHIRResourcePropertyPath(),
                            'allowed_values': element.allowedValues.val(),
                        };
                        postProperties.push(data);
                    } else {
                        currentGroup = element.name;
                    }
                });
                self.saveButton.ajax({
                    url: casePropertyUrl,
                    type: 'POST',
                    dataType: 'JSON',
                    data: {
                        'properties': JSON.stringify(postProperties),
                        'fhir_resource_type': self.fhirResourceType(),
                        'remove_fhir_resource_type': self.removefhirResourceType(),
                        'case_type': self.activeCaseType(),
                    },
                    success: function () {
                        var activeCaseType = self.getActiveCaseType();
                        activeCaseType.properties(self.casePropertyList());
                    },
                    // Error handling is managed by SaveButton logic in main.js
                });
            },
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        self.init = function (callback) {
            $.getJSON(dataUrl)
                .done(function (data) {
                    _.each(data.case_types, function (caseTypeData) {
                        var caseTypeObj = caseType(caseTypeData.name, caseTypeData.fhir_resource_type);
                        var groupDict = _.groupBy(caseTypeData.properties, function (prop) {return prop.group;});
                        caseTypeObj.init(groupDict, changeSaveButton);
                        self.caseTypes.push(caseTypeObj);
                    });
                    if (self.caseTypes().length) {
                        self.goToCaseType(self.caseTypes()[0]);
                    }
                    self.casePropertyList.subscribe(changeSaveButton);
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
                    return caseType.properties();
                }
            }
            return [];
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
            self.casePropertyList(self.activeCaseTypeData());
            self.saveButton.setState('saved');
        };

        self.newCaseProperty = function () {
            if (_.isString(self.newPropertyName())) {
                var prop = propertyListItem(self.newPropertyName(), false, '', self.activeCaseType(), '', '', {});
                prop.dataType.subscribe(changeSaveButton);
                prop.description.subscribe(changeSaveButton);
                prop.fhirResourcePropPath.subscribe(changeSaveButton);
                prop.deprecated.subscribe(changeSaveButton);
                prop.removeFHIRResourcePropertyPath.subscribe(changeSaveButton);
                prop.allowedValues.on('change', changeSaveButton);
                self.newPropertyName(undefined);
                self.casePropertyList.push(prop);
            }
        };

        self.newGroup = function () {
            if (_.isString(self.newGroupName())) {
                var group = propertyListItem(self.newGroupName(), true, '', self.activeCaseType());
                self.casePropertyList.push(group);
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

        // CREATE workflow
        self.name = ko.observable("").extend({
            rateLimit: { method: "notifyWhenChangesStop", timeout: 400, }
        });

        self.nameValid = ko.observable(false);
        self.nameChecked = ko.observable(false);
        self.name.subscribe((value) => {
            if (!value) {
                return;
            }
            let existing = _.find(self.caseTypes(), function (prop) {
                return prop.name === value;
            });
            self.nameValid(!existing);
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
