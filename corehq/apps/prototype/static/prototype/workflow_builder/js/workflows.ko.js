/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.workflows', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');

    var BaseWorkflow = function (app, workflowType) {
        var self = this;
        utils.BaseAppObj.call(self);

        self.name('Untitled Workflow');
        self.distance = ko.observable(0);
        self.isSelected = ko.observable(false);
        self.workflowType = ko.observable(workflowType);

        self.app = app;

        self.containers = ko.observableArray();

        self.containerTemplate = function (container) {
            return container.templateId();
        };

        self.updateDistance = function () {
            var $W = $("#workspace"),
                $UI = $('#' + self.draggableId());
            var dist = Math.abs(Math.round(Math.sqrt(
                ($W.scrollLeft() + $UI.position().left)^2 +
                ($W.scrollTop() + $UI.position().top)^2
            )));
            self.distance(dist);
        };

    };
    BaseWorkflow.prototype = Object.create(utils.BaseAppObj.prototype);

    module.WorkflowA = function (app) {
        var self = this;
        BaseWorkflow.call(self, app, utils.WorkflowType.SURVEY);
        self.containers.push(new FormContainer(
            self, utils.FormType.SURVEY, utils.FormContainerTemplate.SURVEY
        ));
    };
    module.WorkflowA.prototype = Object.create(BaseWorkflow.prototype);

    module.WorkflowB = function (app) {
        var self = this;
        BaseWorkflow.call(self, app, utils.WorkflowType.FOLLOWUP);
        self.containers.push(new FormContainer(
            self, utils.FormType.REGISTRATION, utils.FormContainerTemplate.REGISTRATION
        ));
        self.containers.push(new FormContainer(
            self, utils.FormType.FOLLOWUP, utils.FormContainerTemplate.FOLLOWUP_ONLY
        ));
    };
    module.WorkflowB.prototype = Object.create(BaseWorkflow.prototype);

    module.WorkflowC = function (app) {
        var self = this;
        BaseWorkflow.call(self, app, utils.WorkflowType.COMPLETE);
        self.containers.push(new FormContainer(
            self, utils.FormType.REGISTRATION, utils.FormContainerTemplate.REGISTRATION
        ));
        self.containers.push(new FormContainer(
            self, utils.FormType.FOLLOWUP, utils.FormContainerTemplate.FOLLOWUP
        ));
        self.containers.push(new FormContainer(
            self, utils.FormType.COMPLETION, utils.FormContainerTemplate.COMPLETION
        ));
    };
    module.WorkflowC.prototype = Object.create(BaseWorkflow.prototype);

    var FormContainer = function (workflow, formType, templateId) {
        var self = this;
        self.workflow = workflow;
        self.formType = ko.observable(formType);
        self.templateId = ko.observable(templateId);
        self.isSelected = ko.observable(false);

        self.addForm = function () {
            self.workflow.app.addForm(self);
        };
        
        self.selector = ko.computed(function (){
            return '#' + self.workflow.draggableId()
                + ' .' + utils.FormContainerClass[self.formType()];
        });

        self.handleFormDrop = function (event, ui) {
            var $form = $(ui.draggable);
            $form.css("top", 0);
            $form.css("left", 0);
            $(this).find('.workflow-new-form').before($form);
            var formUuid =_ .last($form.attr('id').split('_'));
            var matchingForm = _.first(_.filter(self.workflow.app.forms(), function (f) {
                return f.uuid() === formUuid;
            }));
            matchingForm.container = self;
            matchingForm.isRegForm(self.formType() === utils.FormType.REGISTRATION);
            matchingForm.updateOrder();
        };
    };

    return module;
});
