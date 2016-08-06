/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.preview', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');

    module.AppPreview = function (app) {
        var self = this;
        self.app = app;
        self.screens = ko.observableArray();
        self.workflowScreen = new SelectWorkflowScreen(self);
        self.formScreen = new FormScreen(self);
        self.regFromScreen = new RegistrationFormScreen(self);
        self.recordListScreen = new RecordListScreen(self);
        self.editRecordScreen = new EditRecordScreen(self);
        self.confirmFormScreen = new ConfirmFormScreen(self);
        self.history = ko.observableArray();

        self.isShown = ko.observable(true);
        self.focusedItem = ko.observable();

        self.init = function () {
            self.screens.push(self.workflowScreen);
            self.screens.push(self.formScreen);
            self.screens.push(self.regFromScreen);
            self.screens.push(self.recordListScreen);
            self.screens.push(self.editRecordScreen);
            self.screens.push(self.confirmFormScreen);

            self.history.push(self.workflowScreen);
        };

        self.toggleShown = function () {
            self.isShown(!self.isShown());
            $(window).trigger('preview.resize', self.isShown());
        };

        self.screenTemplate = function (screen) {
            return screen.templateId();
        };

        self.hideAllScreens = function () {
            _.each(self.screens(), function (s) {
                s.isSelected(false);
            });
        };

        self.isBackVisible = ko.computed(function() {
            return self.history().length > 1;
        });

        self.goBack = function () {
            if (self.isBackVisible()) {
                self.hideAllScreens();
                self.history.pop();
                self.focusedItem(null);
                _.last(self.history()).isSelected(true);
            }
        };

        self.resetApp = function () {
            self.hideAllScreens();
            self.history.removeAll();
            self.workflowScreen.isSelected(true);

            self.history.push(self.workflowScreen);
        };

        self.selectNextScreen = function (workflow) {
            if (workflow.workflowType() === utils.WorkflowType.SURVEY) {
                self.hideAllScreens();
                self.formScreen.form(workflow.form());
                self.focusedItem(workflow.form());
                self.formScreen.isSelected(true);

                self.history.push(self.formScreen);
            } else {
                self.hideAllScreens();
                self.recordListScreen.selectedWorkflow(workflow);
                self.focusedItem(workflow);
                self.recordListScreen.isSelected(true);

                self.history.push(self.recordListScreen);
            }
        };

        self.selectRecord = function (workflow, record) {
            self.hideAllScreens();
            self.editRecordScreen.selectedWorkflow(workflow);
            self.editRecordScreen.selectedRecord(record);
            self.editRecordScreen.isSelected(true);
            self.focusedItem(workflow);

            self.history.push(self.editRecordScreen);
        };

        self.selectForm = function (form) {
            self.hideAllScreens();
            self.formScreen.form(form);
            self.focusedItem(form);
            self.formScreen.isSelected(true);

            self.history.push(self.formScreen);
        };

        self.selectRegistrationForm = function (form) {
            self.hideAllScreens();
            self.regFromScreen.form(form);
            self.focusedItem(form);
            self.regFromScreen.isSelected(true);
            self.regFromScreen.recordName(null);

            self.history.push(self.regFromScreen);
        };

        self.confirmSubmission = function () {
            self.hideAllScreens();
            self.focusedItem(null);
            self.confirmFormScreen.isSelected(true);

            self.history.push(self.confirmFormScreen);
        };

    };

    var BaseScreen = function (templateId, isSelected, preview) {
        var self = this;
        self.preview = preview;
        self.templateId = ko.observable(templateId);
        self.isSelected = ko.observable(isSelected);
        self.isHidden = ko.computed(function () {
            return !self.isSelected();
        });
    };

    var SelectWorkflowScreen = function (preview) {
        var self = this;
        BaseScreen.call(self, 'ko-template-screen-workflows', true, preview);
        self.workflows = ko.computed(function () {
            return self.preview.app.workflows();
        });

        self.selectNextScreen = function (workflow) {
            self.preview.selectNextScreen(workflow);
        };
    };
    SelectWorkflowScreen.prototype = Object.create(BaseScreen.prototype);

    var FormScreen = function (preview) {
        var self = this;
        BaseScreen.call(
            self,
            'ko-template-screen-questions',
            false,
            preview
        );

        self.form = ko.observable();
        self.hasForm = ko.computed(function () {
            return !!self.form();
        });

        self.title = ko.computed(function () {
            if (self.form()) {
                return self.form().name();
            }
            return "Unititled Form";
        });

        self.formPreviewTemplate = function (form) {
            return form.previewTemplate();
        };

        self.saveForm = function () {
            self.preview.confirmSubmission();
        };

        self.cancel = function () {
            self.preview.goBack();
        };
    };
    FormScreen.prototype = Object.create(BaseScreen.prototype);

    var RegistrationFormScreen = function (preview) {
        var self = this;
        FormScreen.call(
            self,
            preview
        );

        self.recordName = ko.observable();

        self.disableSave = ko.computed(function() {
            return self.recordName() === null || self.recordName() === undefined;
        });

        self.saveForm = function () {
            self.form().testRecords.push(self.recordName());
            self.recordName(null);
            self.cancel();
        };

    };
    RegistrationFormScreen.prototype = Object.create(FormScreen.prototype);


    var RecordListScreen = function (preview) {
        var self = this;
        BaseScreen.call(
            self,
            'ko-template-screen-recordlist',
            false,
            preview
        );
        self.selectedWorkflow = ko.observable();

        self.title = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().name();
            }
            return "Untitled Workflow";
        });

        self.registrationForm = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().registrationForm();
            }
            return null;
        });

        self.hasRegistrationForm = ko.computed(function () {
            return self.registrationForm() !== null;
        });

        self.records = ko.computed(function () {
            var records = [];
            if (self.selectedWorkflow()) {
                records = self.selectedWorkflow().registrationForm().testRecords();
            }
            return records;
        });

        self.thingName = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().thingName();
            }
            return "Record";
        });

        self.selectRecord = function (record) {
            self.preview.selectRecord(self.selectedWorkflow(), record);
        };

        self.selectForm = function (form) {
            self.preview.selectRegistrationForm(form);
        };

    };
    RecordListScreen.prototype = Object.create(BaseScreen.prototype);

    var EditRecordScreen = function (preview) {
        var self = this;
        BaseScreen.call(
            self,
            'ko-template-screen-editrecord',
            false,
            preview
        );
        self.selectedWorkflow = ko.observable();
        self.selectedRecord = ko.observable();

        self.title = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().thingName() + ' "' + self.selectedRecord() + '"';
            }
            return "Untitled Workflow";
        });

        self.forms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms = self.selectedWorkflow().followupForms();
            }
            return relevantForms;
        });

        self.selectForm = function (form) {
            self.preview.selectForm(form);
        };
    };
    EditRecordScreen.prototype = Object.create(BaseScreen.prototype);

    var ConfirmFormScreen = function (preview) {
        var self = this;
        BaseScreen.call(
            self,
            'ko-template-screen-confirmform',
            false,
            preview
        );

        self.confirm = function () {
            self.preview.resetApp();
        };
    };
    ConfirmFormScreen.prototype = Object.create(BaseScreen.prototype);



    return module;
});
