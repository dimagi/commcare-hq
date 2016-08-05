/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.workflows', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');
    var forms = hqImport('prototype.workflow_builder.forms');

    var BaseWorkflow = function (
        name, app, navTemplate, editTemplate, modalTemplate, workflowType
    ) {
        var self = this;
        utils.BaseAppObj.call(self, name, app, navTemplate, editTemplate, modalTemplate);

        self.workflowType = ko.observable(workflowType);
        self.remove = function () {
            self.parent.removeWorkflow(self);
        };
    };
    BaseWorkflow.prototype = Object.create(utils.BaseAppObj.prototype);

    module.Survey = function (name, app) {
        var self = this;
        BaseWorkflow.call(
            self,
            name,
            app,
            'ko-template-nav-survey',
            'ko-template-edit-survey',
            'ko-template-modal-survey',
            utils.WorkflowType.SURVEY
        );

        self.form = ko.observable(new forms.Form(name, self));
    };
    module.Survey.prototype = Object.create(BaseWorkflow.prototype);

    module.RecordList = function (name, app) {
        var self = this;
        BaseWorkflow.call(
            self,
            name,
            app,
            'ko-template-nav-recordlist',
            'ko-template-edit-recordlist',
            'ko-template-modal-recordlist',
            utils.WorkflowType.RECORD_LIST
        );

        // for this prototype we're only allowing one registration form
        self.registrationForm = ko.observable(new forms.RegistrationForm("Create Record", self));

        self.followupForms = ko.observableArray();
        self.followupForms.push(new forms.FollowupForm("Update Record", self));
        self.followupFormNavTemplate = function (form) {
            return form.navTemplate();
        };
        self.followupFormModalTemplate = function (form) {
            return form.modalTemplate();
        };

        self.followupCounter = ko.observable(2);

        self.addForm = function () {
            self.followupForms.push(new forms.FollowupForm("Update Record " + self.followupCounter(), self));
            self.followupCounter(self.followupCounter() + 1);
        };

        self.removeForm = function (form) {
            $('#' + form.deleteModalId()).one('hidden.bs.modal', function () {
                self.followupForms.remove(form);
            });
        };
    };
    module.RecordList.prototype = Object.create(BaseWorkflow.prototype);

    return module;
});
