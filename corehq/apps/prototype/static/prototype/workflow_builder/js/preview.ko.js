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
                _.first(workflow.containers()).isSelected(true);
            }
        };

        self.selectRecord = function (workflow, record) {
            self.hideAllScreens();
            self.editRecordScreen.selectedWorkflow(workflow);
            self.editRecordScreen.selectedRecord(record);
            self.editRecordScreen.isSelected(true);

            self.history.push(self.editRecordScreen);
            workflow.containers()[1].isSelected(true);
            _.last(workflow.containers()).isSelected(true);
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
            console.log('edit form');
            console.log(record);
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
        self.orderedWorkflows = ko.computed(function () {
            return _.sortBy(self.preview.app.workflows(), function (wf) {
                return wf.distance();
            });
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
                relevantForms = _.filter(self.preview.app.forms(), function (f) {
                    return f.container.formType() === utils.FormType.REGISTRATION && f.container.workflow.uuid() === self.selectedWorkflow().uuid();
                });
                relevantForms = _.sortBy(relevantForms, function (f) {
                    return f.order();
                });
            }
            return relevantForms;
        });

        self.cleanup = function () {
            if (self.selectedWorkflow()) {
                self.selectedWorkflow().isSelected(false);
                _.first(self.selectedWorkflow().containers()).isSelected(false);
            }
        };

        self.selectForm = function (form) {
            self.preview.selectForm(form);
            form.isSelected(true);
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

        self.followupForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms = _.filter(self.preview.app.forms(), function (f) {
                    return f.container.formType() === utils.FormType.FOLLOWUP && f.container.workflow.uuid() === self.selectedWorkflow().uuid();
                });
                relevantForms = _.sortBy(relevantForms, function (f) {
                    return f.order();
                });
            }
            return relevantForms;
        });

        self.completeForms = ko.computed(function () {
            var relevantForms = [];
            if (self.selectedWorkflow()) {
                relevantForms = _.filter(self.preview.app.forms(), function (f) {
                    return f.container.formType() === utils.FormType.COMPLETION && f.container.workflow.uuid() === self.selectedWorkflow().uuid();
                });
                relevantForms = _.sortBy(relevantForms, function (f) {
                    return f.order();
                });
            }
            return relevantForms;
        });

        self.hasCompleteForms = ko.computed(function () {
            return self.completeForms().length > 0;
        });

        self.cleanup = function () {
            if (self.selectedWorkflow()) {
                _.each(self.selectedWorkflow().containers(), function (c) {
                    c.isSelected(false);
                });
                _.first(self.selectedWorkflow().containers()).isSelected(true);
            }
        };

        self.selectForm = function (form) {
            self.preview.selectEditForm(form, self.selectedRecord());
            form.isSelected(true);
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
                relevantForms = _.filter(self.preview.app.forms(), function (f) {
                    return f.container.workflow.uuid() === self.selectedWorkflow().uuid();
                });
                relevantForms = _.sortBy(relevantForms, function (f) {
                    return f.order();
                });
            }
            return relevantForms;
        });

        self.cleanup = function () {
            if (self.selectedWorkflow()) {
                self.selectedWorkflow().isSelected(false);
            }
        };

        self.selectForm = function (form) {
            self.preview.selectForm(form);
            form.isSelected(true);
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
            return self.forms().length > 0 && _.first(self.forms()).container.formType() === utils.FormType.REGISTRATION && !self.hasName();
        });

        self.saveForm = function () {
            if (self.forms().length > 0 && _.first(self.forms()).container.formType() === utils.FormType.REGISTRATION) {
                _.each(self.preview.recordListScreen.registerForms(), function (f) {
                    f.records.push(self.recordName() || "Untitled Record");
                });
                self.recordName(null);
            } else if (self.forms().length > 0 && _.first(self.forms()).container.formType() === utils.FormType.COMPLETION) {
                _.each(self.preview.recordListScreen.registerForms(), function (f) {
                    f.records.remove(self.recordName());
                });
                _.each(_.first(self.preview.recordListScreen.registerForms()).container.workflow.containers(), function (c) {
                    c.isSelected(false);
                });
                self.recordName(null);
                self.preview.goBack();
                self.preview.goBack();
            }
            self.cancel();
        };

        self.cancel = function () {
            self.preview.goBack();
        };

        self.cleanup = function () {
            _.each(self.forms(), function (f) {
                f.isSelected(false);
            });
        };
    };
    FormScreen.prototype = Object.create(BaseScreen.prototype);


    return module;
});
