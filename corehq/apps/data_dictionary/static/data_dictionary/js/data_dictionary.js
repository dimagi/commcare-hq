define([
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/main",
    "analytix/js/google",
    "hqwebapp/js/knockout_bindings.ko",
], function(
    $,
    ko,
    _,
    initialPageData,
    hqMain,
    googleAnalytics
) {
    var CaseType = function (name) {
        var self = this;
        self.name = name;
        self.properties = ko.observableArray();

        self.init = function (group_dict, changeSaveButton) {
            _.each(group_dict, function (properties, group) {
                var groupObj = new PropertyListItem(group, true, group, self.name);
                self.properties.push(groupObj);
                _.each(properties, function (prop) {
                    var propObj = new PropertyListItem(prop.name, false, prop.group, self.name, prop.data_type, prop.description, prop.deprecated);
                    propObj.description.subscribe(changeSaveButton);
                    propObj.dataType.subscribe(changeSaveButton);
                    propObj.deprecated.subscribe(changeSaveButton);
                    self.properties.push(propObj);
                });
            });
        };
    };

    var PropertyListItem = function (name, isGroup, groupName, caseType, dataType, description, deprecated) {
        var self = this;
        self.name = name;
        self.expanded = ko.observable(true);
        self.isGroup = isGroup;
        self.group = ko.observable(groupName);
        self.caseType = caseType;
        self.dataType = ko.observable(dataType);
        self.description = ko.observable(description);
        self.deprecated = ko.observable(deprecated || false);

        self.toggle = function () {
            self.expanded(!self.expanded());
        };

        self.deprecateProperty = function () {
            self.deprecated(true);
        };

        self.restoreProperty = function () {
            self.deprecated(false);
        };
    };

    var DataDictionaryModel = function (dataUrl, casePropertyUrl, typeChoices) {
        var self = this;
        self.caseTypes = ko.observableArray();
        self.activeCaseType = ko.observable();
        self.newPropertyName = ko.observable();
        self.newGroupName = ko.observable();
        self.casePropertyList = ko.observableArray();
        self.showAll = ko.observable(false);
        self.availableDataTypes = typeChoices;
        self.saveButton = hqMain.initSaveButton({
            unsavedMessage: gettext("You have unsaved changes to your data dictionary."),
            save: function() {
                var postProperties = [];
                var currentGroup = '';
                _.each(self.casePropertyList(), function(element) {
                    if (!element.isGroup) {
                        var data = {
                            'caseType': element.caseType,
                            'name': element.name,
                            'data_type': element.dataType(),
                            'group': currentGroup,
                            'description': element.description(),
                            'deprecated': element.deprecated(),
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
                    },
                    success: function() {
                        var activeCaseType = self.getActiveCaseType();
                        activeCaseType.properties(self.casePropertyList());
                    },
                    error: function() {
                        throw gettext("There was an error saving");
                    },
                });
            },
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        self.init = function () {
            $.getJSON(dataUrl)
                .done(function (data) {
                    _.each(data.case_types, function (caseType) {
                        var caseTypeObj = new CaseType(caseType.name);
                        var groupDict = _.groupBy(caseType.properties, function(prop) {return prop.group;});
                        caseTypeObj.init(groupDict, changeSaveButton);
                        self.caseTypes.push(caseTypeObj);
                    });
                    if (self.caseTypes().length) {
                        self.goToCaseType(self.caseTypes()[0]);
                    }
                    self.casePropertyList.subscribe(changeSaveButton);
                });
        };

        this.getActiveCaseType = function () {
            return _.find(self.caseTypes(), function (prop) {
                return prop.name === self.activeCaseType();
            });
        };

        this.activeCaseTypeData = function () {
            var caseTypes = self.caseTypes();
            if (caseTypes.length) {
                var caseType = self.getActiveCaseType();
                if (caseType) {
                    return caseType.properties();
                }
            }
            return [];
        };

        this.goToCaseType = function (caseType) {
            if (self.saveButton.state === 'save') {
                var dialog = confirm('You have unsaved changes to this case type. Are you sure you would like to continue?');
                if (!dialog) {
                    return;
                }
            }
            self.activeCaseType(caseType.name);
            self.casePropertyList(self.activeCaseTypeData());
            self.saveButton.setState('saved');
        };

        this.newCaseProperty = function () {
            var prop = new PropertyListItem(self.newPropertyName(), false, '', self.activeCaseType());
            prop.dataType.subscribe(changeSaveButton);
            prop.description.subscribe(changeSaveButton);
            prop.deprecated.subscribe(changeSaveButton);
            self.newPropertyName('');
            self.casePropertyList.push(prop);
        };

        this.newGroup = function () {
            var group = new PropertyListItem(self.newGroupName(), true, '', self.activeCaseType());
            self.casePropertyList.push(group);
            self.newGroupName('');
        };

        this.toggleGroup = function (group) {
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

        this.showDeprecated = function () {
            self.showAll(true);
        };

        this.hideDeprecated = function () {
            self.showAll(false);
        };
    };

    $(function() {
        var dataUrl = initialPageData.reverse('data_dictionary_json'),
            casePropertyUrl = initialPageData.reverse('update_case_property'),
            typeChoices = initialPageData.get('typeChoices'),
            viewModel = new DataDictionaryModel(dataUrl, casePropertyUrl, typeChoices);
        viewModel.init();
        $('#hq-content').parent().koApplyBindings(viewModel);
        $('#download-dict').click(function() {
            googleAnalytics.track.event('Data Dictionary', 'downloaded data dictionary');
        });
    });
});
