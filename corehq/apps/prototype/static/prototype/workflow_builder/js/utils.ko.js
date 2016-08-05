hqDefine('prototype.workflow_builder.utils', function () {
    'use strict';
    var module = {};
    var _private = {};

    _private.generateUUID = function() {
        var d = new Date().getTime();
        var uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = (d + Math.random()*16)%16 | 0;
            d = Math.floor(d/16);
            return (c=='x' ? r : (r&0x3|0x8)).toString(16);
        });
        return uuid;
    };

    module.WorkflowType = {
        SURVEY: 'Survey',
        RECORD_LIST: 'Record List',
    };

    module.FormType = {
        SURVEY: 'SURVEY',
        REGISTRATION: 'REGISTRATION',
        FOLLOWUP: 'FOLLOWUP',
    };

    module.BaseAppObj = function (name, app, navTemplate, editTemplate, modalTemplate) {
        var self = this;
        self.uuid = ko.observable(_private.generateUUID());
        self.name = ko.observable(name);
        self.app = app;

        self.isFocusedInPreview = ko.observable(false);
        self.isInEditMode = ko.computed(function () {
            return self.app.editItem().uuid() === self.uuid();
        });

        self.navTemplate = ko.observable(navTemplate);
        self.editTemplate = ko.observable(editTemplate);
        self.modalTemplate = ko.observable(modalTemplate);

        self.settingsId = ko.computed(function () {
            return 'settings_' + self.uuid();
        });
        self.menuId = ko.computed(function () {
            return 'menu_' + self.uuid();
        });
        self.deleteModalId = ko.computed(function () {
            return 'delete_' + self.uuid();
        });
    };


    module.getNameFromCounter = function (name, count) {
        if (count > 1) {
            name = name + ' ' + count;
        }
        return name;
    };


    return module;
});
