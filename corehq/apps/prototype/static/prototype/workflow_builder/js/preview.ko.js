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
        self.surveyScreen = new SelectSurveyScreen(self);
        self.formScreen = new FormScreen(self);
        self.recordListScreen = new RecordListScreen(self);
        self.editRecordScreen = new EditRecordScreen(self);
        self.history = ko.observableArray();

        self.isShown = ko.observable(true);

        self.init = function () {
            self.screens.push(self.workflowScreen);
            self.screens.push(self.surveyScreen);
            self.screens.push(self.formScreen);
            self.screens.push(self.recordListScreen);
            self.screens.push(self.editRecordScreen);

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
                var poppedWf = self.history.pop();
                poppedWf.cleanup();
                _.last(self.history()).isSelected(true);
            }
        };

        self.resetApp = function () {
            self.hideAllScreens();
            self.history.removeAll();
            self.history.push(self.workflowScreen);
            self.workflowScreen.isSelected(true);
        };

        self.selectWorkflow = function (workflow) {
            if (workflow.workflowType() === utils.WorkflowType.SURVEY) {
                self.hideAllScreens();
                self.surveyScreen.selectedWorkflow(workflow);
                self.surveyScreen.isSelected(true);

                self.history.push(self.surveyScreen);
            } else {
                self.hideAllScreens();
                self.recordListScreen.selectedWorkflow(workflow);
                self.recordListScreen.isSelected(true);

                self.history.push(self.recordListScreen);
            }
        };

        self.selectRecord = function (workflow, record) {
            self.hideAllScreens();
            self.editRecordScreen.selectedWorkflow(workflow);
            self.editRecordScreen.selectedRecord(record);
            self.editRecordScreen.isSelected(true);

            self.history.push(self.editRecordScreen);
        };

        self.selectForm = function (form) {
            self.hideAllScreens();
            self.formScreen.forms.removeAll();
            self.formScreen.forms.push(form);
            self.formScreen.isSelected(true);
            self.formScreen.recordName(null);

            self.history.push(self.formScreen);
        };

        self.selectEditForm = function (form, record) {
            self.selectForm(form);
            self.formScreen.recordName(record);
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

        self.selectWorkflow = function (workflow) {
            self.preview.selectWorkflow(workflow);
            workflow.isSelected(true);
        };

        self.cleanup = function () {
            // todo
        };
    };
    SelectWorkflowScreen.prototype = Object.create(BaseScreen.prototype);

    var RecordListScreen = function (preview) {
        var self = this;
        BaseScreen.call(self, 'ko-template-screen-recordlist', false, preview);
        self.selectedWorkflow = ko.observable();

        self.workflowName = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().name();
            }
            return "Untitled Workflow";
        });

        self.registerForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms.push(self.selectedWorkflow().registrationForm());
            }
            return relevantForms;
        });

        self.cleanup = function () {
            // todo
        };

        self.selectForm = function (form) {
            self.preview.selectForm(form);
            // todo
        };

        self.selectRecord = function (record) {
            self.preview.selectRecord(self.selectedWorkflow(), record);
        };
    };
    RecordListScreen.prototype = Object.create(BaseScreen.prototype);

    var EditRecordScreen = function (preview) {
        var self = this;
        BaseScreen.call(self, 'ko-template-screen-editrecord', false, preview);
        self.selectedWorkflow = ko.observable();
        self.selectedRecord = ko.observable();

        self.workflowName = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().name();
            }
            return "Untitled Workflow";
        });

        self.registrationForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms.push(self.selectedWorkflow().registrationForm());
            }
            return null;
        });

        self.followupForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms = _.filter(self.selectedWorkflow().followupForms(), function (f) {
                    return f.isFollowupForm();
                });
            }
            return relevantForms;
        });

        self.completeForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms = _.filter(self.selectedWorkflow().followupForms(), function (f) {
                    return f.isCompletionForm();
                });
            }
            return relevantForms;
        });

        self.hasCompleteForms = ko.computed(function () {
            return self.completeForms().length > 0;
        });

        self.cleanup = function () {
            // todo handle side nav highlight
        };

        self.selectForm = function (form) {
            self.preview.selectEditForm(form, self.selectedRecord());
            // todo handle side nav highlight
        };
    };
    EditRecordScreen.prototype = Object.create(BaseScreen.prototype);

    var SelectSurveyScreen = function (preview) {
        var self = this;
        BaseScreen.call(self, 'ko-template-screen-survey', false, preview);

        self.selectedWorkflow = ko.observable();

        self.workflowName = ko.computed(function () {
            if (self.selectedWorkflow()) {
                return self.selectedWorkflow().name();
            }
            return "Untitled Workflow";
        });

        self.forms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms.push(self.selectedWorkflow().form());
            }
            return relevantForms;
        });

        self.cleanup = function () {
            // todo handle side nav highlight
        };

        self.selectForm = function (form) {
            self.preview.selectForm(form);
            // todo handle side nav highlight
        };
    };
    SelectSurveyScreen.prototype = Object.create(BaseScreen.prototype);

    var FormScreen = function (preview) {
        var self = this;
        BaseScreen.call(self, 'ko-template-screen-questions', false, preview);
        self.forms = ko.observableArray();
        self.recordName = ko.observable();
        self.hasName = ko.computed(function () {
           return !_.isEmpty(self.recordName());
        });
        self.disableSave = ko.computed(function () {
            // todo
        });

        self.saveForm = function () {
            //todo
            // if (self.forms().length > 0 && _.first(self.forms()).container.formType() === utils.FormType.REGISTRATION) {
            //     _.each(self.preview.recordListScreen.registerForms(), function (f) {
            //         f.records.push(self.recordName() || "Untitled Record");
            //     });
            //     self.recordName(null);
            // } else if (self.forms().length > 0 && _.first(self.forms()).container.formType() === utils.FormType.COMPLETION) {
            //     _.each(self.preview.recordListScreen.registerForms(), function (f) {
            //         f.records.remove(self.recordName());
            //     });
            //     _.each(_.first(self.preview.recordListScreen.registerForms()).container.workflow.containers(), function (c) {
            //         c.isSelected(false);
            //     });
            //     self.recordName(null);
            //     self.preview.goBack();
            //     self.preview.goBack();
            // }
            self.cancel();
        };

        self.cancel = function () {
            self.preview.goBack();
        };

        self.cleanup = function () {
            // todo handle side nav highlight
        };
    };
    FormScreen.prototype = Object.create(BaseScreen.prototype);


    return module;
});
