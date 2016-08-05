/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.workflowBuilder', function () {
   'use strict';
    var module = {};

    var utils = hqImport('prototype.workflow_builder.utils'),
        forms = hqImport('prototype.workflow_builder.forms'),
        workflows = hqImport('prototype.workflow_builder.workflows'),
        preview = hqImport('prototype.workflow_builder.preview');

    module.AppViewModel = function () {
        var self = this;
        self.name = ko.observable('My New App');
        self.appSettings = new EditAppSettings(self);
        self.isEditingSettings = ko.computed(function () {
            return self.appSettings.isInEditMode();
        });

        self.init = function () {
            self.appPreview = ko.observable(new preview.AppPreview(self));
            self.appPreview().init();
            $('#js-add-new-item')
                .on('workflowBuilder.add.survey', self.createSurvey)
                .on('workflowBuilder.add.recordlist', self.createRecordList);
        };

        self.workflows = ko.observableArray();
        self.workflowNavTemplate = function (item) {
            return item.navTemplate();
        };
        self.workflowModalTemplate = function (item) {
            return item.modalTemplate();
        };

        self.editItem = ko.observable(self.appSettings);
        self.setEditItem = function (item) {
            self.appSettings.isInEditMode(false);
            self.editItem(item);
        };
        self.editItemTemplate = function (item) {
            return ko.utils.unwrapObservable(item).editTemplate();
        };
        self.editAppSettings = function () {
            self.appSettings.isInEditMode(true);
            self.editItem(self.appSettings);
        };

        self.surveyCounter = ko.observable(1);
        self.recordListCounter = ko.observable(1);

        self.hasNoWorkflows = ko.computed(function () {
            return self.workflows().length === 0;
        });

        self.createSurvey = function () {
            var wf = new workflows.Survey(utils.getNameFromCounter("Survey Questions", self.surveyCounter()), self);
            self.workflows.push(wf);
            self.setEditItem(wf.form());
            self.surveyCounter(self.surveyCounter() + 1);
            self.appPreview().resetApp();
        };

        self.createRecordList = function () {
            var wf = new workflows.RecordList(utils.getNameFromCounter("Record List", self.recordListCounter()), self);
            self.workflows.push(wf);
            self.setEditItem(wf);
            self.surveyCounter(self.recordListCounter() + 1);
            self.appPreview().resetApp();
        };

        self.removeWorkflow = function (workflow) {
            $('#' + workflow.deleteModalId()).one('hidden.bs.modal', function () {
                self.workflows.remove(workflow);
            });
        };

    };

    var EditAppSettings = function (app) {
        var self = this;
        self.app = app;
        self.editTemplate = ko.observable('ko-template-edit-appsettings');
        self.isInEditMode = ko.observable(true);
        self.uuid = ko.observable('appsettings');
    };

    return module;
});
