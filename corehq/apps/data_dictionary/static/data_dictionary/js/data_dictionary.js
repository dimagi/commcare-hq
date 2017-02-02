/* globals django */
(function ($, _) {
    // var CaseProperty = function (caseType, data, casePropertyUrl) {
    //     var self = this;
    //
    //     self.caseType = ko.observable(caseType);
    //     self.name = ko.observable(data.name);
    //     self.description = ko.observable(data.description);
    //     self.dataType = ko.observable(data.data_type);
    //     self.group = ko.observable(data.group);
    //     self.availableDataTypes = ko.observableArray([
    //         {value: 'date', display: django.gettext('Date')},
    //         {value: 'plain', display: django.gettext('Plain')},
    //         {value: 'number', display: django.gettext('Number')},
    //         {value: 'select', display: django.gettext('Select')},
    //         {value: 'integer', display: django.gettext('Integer')},
    //     ]);
    //     self.isVisible = ko.observable(true);
    //     self.isGroup = false;
    //
    //
    //     self.dataType.subscribe(function (newType) {
    //         if (newType) {
    //             self.saveCaseProperty(self.name(), newType)
    //         }
    //     }, self);
    //
    //     self.saveCaseProperty = function (name, type) {
    //         $.ajax({
    //                 url: casePropertyUrl,
    //                 type: 'POST',
    //                 dataType: 'JSON',
    //                 data: {
    //                     'caseType': self.caseType(),
    //                     'name': name,
    //                     'data_type': type,
    //                 },
    //                 success: function () { },
    //                 // todo show errors
    //                 error: function () { },
    //         });
    //     };
    // };

    var CaseType = function (name) {
        var self = this;
        self.name = ko.observable(name);
        self.properties = ko.observableArray();
        // self.groups = ko.observableArray();

        // self.init = function (group_dict) {
        //     _.each(group_dict, function (properties, group) {
        //         var groupObj = new CasePropertyGroup(group, casePropertyUrl);
        //         groupObj.init(properties);
        //         self.groups.push(groupObj);
        //     });
        // };

        self.init = function (group_dict, changeSaveButton) {
            _.each(group_dict, function (properties, group) {
                var groupObj = new PropertyListItem(group, true, group, self.name);
                self.properties.push(groupObj);
                _.each(properties, function (prop) {
                    propObj = new PropertyListItem(prop.name, false, prop.group, self.name, prop.data_type, prop.description);
                    propObj.description.subscribe(changeSaveButton);
                    propObj.dataType.subscribe(changeSaveButton);
                    self.properties.push(propObj);
                })
            });
        };
    };

    // var CasePropertyGroup = function (name, casePropertyUrl) {
    //     var self = this;
    //     self.name = ko.observable(name);
    //     self.properties = ko.observableArray();
    //     self.expanded = ko.observable(true);
    //     self.isGroup = true;
    //
    //     self.toggle = function () {
    //         self.expanded(!self.expanded());
    //     };
    //
    //     self.init = function (properties) {
    //         _.each(properties, function (property) {
    //             self.properties.push(new CaseProperty(self.name, property, casePropertyUrl));
    //         });
    //     };
    // };

    var PropertyListItem = function (name, isGroup, groupName, caseType, dataType, description) {
        var self = this;
        self.name = ko.observable(name);
        self.expanded = ko.observable(true);
        self.isGroup = isGroup;
        self.group = ko.observable(groupName);
        self.caseType = caseType;
        self.dataType = ko.observable(dataType);
        self.description = ko.observable(description);
        self.availableDataTypes = ko.observableArray([
            {value: 'date', display: django.gettext('Date')},
            {value: 'plain', display: django.gettext('Plain')},
            {value: 'number', display: django.gettext('Number')},
            {value: 'select', display: django.gettext('Select')},
            {value: 'integer', display: django.gettext('Integer')},
        ]);

        self.toggle = function () {
            self.expanded(!self.expanded());
        };
    };

    var DataDictionaryModel = function (dataUrl, casePropertyUrl) {
        var self = this;
        self.caseTypes = ko.observableArray();
        self.activeCaseType = ko.observable();
        self.newPropertyName = ko.observable();
        self.newGroupName = ko.observable();
        self.casePropertyList = ko.observableArray();
        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes to your data dictionary."),
            save: function() {
                var postProperties = [];
                var currentGroup = '';
                _.each(self.casePropertyList(), function(element) {
                    if (!element.isGroup) {
                        data = {
                            'caseType': element.caseType(),
                            'name': element.name(),
                            'data_type': element.dataType(),
                            'group': currentGroup,
                            'description': element.description()
                        };
                        postProperties.push(data);
                    } else {
                        currentGroup = element.name();
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
                        activeCaseType = self.getActiveCaseType();
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
                    groupDict = _.groupBy(caseType.properties, function(prop) {return prop.group});
                    caseTypeObj.init(groupDict, changeSaveButton);
                    self.caseTypes.push(caseTypeObj);
                });
                self.goToCaseType(self.caseTypes()[0]);
                self.casePropertyList.subscribe(changeSaveButton)
            });
        };

        this.getActiveCaseType = function () {
            return _.find(self.caseTypes(), function (prop) {
                return prop.name() === self.activeCaseType();
            });
        };

        this.activeCaseTypeData = function () {
            var caseTypes = self.caseTypes();
            if (caseTypes.length) {
                caseType = self.getActiveCaseType();
                if (caseType) {
                    return caseType.properties();
                }
            }
            return [];
        };

        this.goToCaseType = function (caseType) {
            if (self.saveButton.state === 'save') {
                dialog = confirm('You have unsaved changes to this case type. Are you sure you would like to continue?');
                if (!dialog) {
                    return;
                }
            }
            self.activeCaseType(caseType.name());
            self.casePropertyList(self.activeCaseTypeData());
            self.saveButton.setState('saved');
        };

        this.newCaseProperty = function () {
            prop = new PropertyListItem(self.newPropertyName(), false, '', self.activeCaseType());
            prop.dataType.subscribe(changeSaveButton);
            self.newPropertyName('');
            self.casePropertyList.push(prop);
        };

        this.newGroup = function () {
            group = new PropertyListItem(self.newGroupName(), true, '', self.activeCaseType());
            self.casePropertyList.push(group);
            self.newGroupName('');
        };

        this.toggleGroup = function (group) {
            group.toggle();
            groupIndex = _.findIndex(self.casePropertyList(), function (element) {
                return element.name() === group.name();
            });
            i = groupIndex + 1;
            next = self.casePropertyList()[i];
            while (!next.isGroup) {
                next.toggle();
                i++;
                next = self.casePropertyList()[i]
            }
        };

        this.debugging = function () {
            debugger;
            alert('done');
        };
    };

    $.fn.initializeDataDictionary = function (dataUrl, casePropertyUrl) {
        var viewModel = new DataDictionaryModel(dataUrl, casePropertyUrl);
        viewModel.init();
        $(this).koApplyBindings(viewModel);
        return viewModel;
    };
})($, _);
