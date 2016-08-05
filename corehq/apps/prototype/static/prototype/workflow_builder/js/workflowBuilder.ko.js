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

        self.editItem = ko.observable();
        self.setEditItem = function (item) {
            self.editItem(item);
        };
        self.editItemTemplate = function (item) {
            return item.editTemplate();
        };

        self.surveyCounter = ko.observable(1);
        self.recordListCounter = ko.observable(1);

        self.hasNoWorkflows = ko.computed(function () {
            return self.workflows().length === 0;
        });

        self.createSurvey = function () {
            self.workflows.push(new workflows.Survey(utils.getNameFromCounter("Survey", self.surveyCounter()), self));
            self.surveyCounter(self.surveyCounter() + 1);
            self.appPreview().resetApp();
        };

        self.createRecordList = function () {
            self.workflows.push(new workflows.RecordList(utils.getNameFromCounter("Record List", self.recordListCounter()), self));
            self.surveyCounter(self.recordListCounter() + 1);
            self.appPreview().resetApp();
        };

        self.removeWorkflow = function (workflow) {
            $('#' + workflow.deleteModalId()).one('hidden.bs.modal', function () {
                self.workflows.remove(workflow);
            });
        };

    };

    return module;
});
