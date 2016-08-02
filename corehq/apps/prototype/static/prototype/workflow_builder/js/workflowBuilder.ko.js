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

            // todo cleanup alert
            $('#workspace').click(function (event) {
                if (!$(event.target).hasClass('workflow-name')) {
                    $('.workflow-name').trigger('workflowBuilder.workflow.deselect');
                }
                if (!$(event.target).hasClass('workflow-form-title')) {
                    $('.workflow-form-title').trigger('workflowBuilder.form.deselect');
                }
            });

        };

        // ------------------
        // WORKFLOWS
        // ------------------

        self.workflows = ko.observableArray();
        self.workflowCounter = ko.observable(1);

        var _addWorkflow = function (wf) {
            self.workflows.push(wf);
            wf.name('Workflow ' + self.workflowCounter());
            self.workflowCounter(self.workflowCounter() + 1);
        };

        self.addWorkflowA = function () {
            _addWorkflow(new workflows.WorkflowA(self));
        };

        self.addWorkflowB = function () {
            _addWorkflow(new workflows.WorkflowB(self));
        };

        self.addWorkflowC= function () {
            _addWorkflow(new workflows.WorkflowC(self));
        };

        self.removeWorkflow = function (workflow) {
            self.workflows.remove(workflow);
        };

        // ------------------
        // Forms
        // ------------------

        self.formCounter = ko.observable(1);
        self.forms = ko.observableArray();

        self.removeForm = function (form) {
            $('#' + form.draggableId()).remove();
            var matchingFormData = _.first(_.filter(self.forms(), function (f) {
                return f.uuid() === form.uuid();
            }));
            self.forms.remove(matchingFormData);
        };
        
        self.addForm = function (container) {
            var form = new forms.Form(container);
            form.name("Form " + self.formCounter());
            self.forms.push(form);
            self.formCounter(self.formCounter() + 1);
        };

        self.printForms = function () {
            console.log(self.forms());
        };

    };

    return module;
});
