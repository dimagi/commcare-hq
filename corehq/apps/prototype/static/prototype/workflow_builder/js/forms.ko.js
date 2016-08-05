/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.forms', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');

    module.Form = function (name, workflow, navTemplate, editTemplate, modalTemplate) {
        var self = this;
        utils.BaseAppObj.call(
            self,
            name,
            workflow,
            navTemplate || 'ko-template-nav-form',
            editTemplate || 'ko-template-edit-form',
            modalTemplate || 'ko-template-modal-form'
        );

        self.questions = ko.observableArray();

        self.addQuestion = function () {
            self.questions.push(new Question(self));
        };

        self.hasNoQuestions = ko.computed(function () {
            return self.questions().length === 0;
        });

        self.remove = function () {
            self.parent.remove();
        };

    };
    module.Form.prototype = Object.create(utils.BaseAppObj.prototype);

    module.RegistrationForm = function (name, workflow) {
        var self = this;
        module.Form.call(
            self,
            name,
            workflow,
            'ko-template-nav-regform',
            'ko-template-edit-regform',
            'ko-template-modal-regform'
        );

        self.recordNameQuestion = ko.observable("What is the name?");
        self.testRecords = ko.observableArray();
    };
    module.RegistrationForm.prototype = Object.create(module.Form.prototype);

    module.FollowupForm = function (name, workflow) {
        var self = this;
        module.Form.call(
            self,
            name,
            workflow,
            'ko-template-nav-followup',
            'ko-template-edit-followup',
            'ko-template-modal-followup'
        );

        self.isCompletionForm = ko.observable(false);
        self.isFollowupForm = ko.computed(function () {
            return !self.isCompletionForm();
        });

        self.remove = function () {
            self.parent.removeForm(self);
        };
    };
    module.RegistrationForm.prototype = Object.create(module.Form.prototype);
    
    var Question = function (form) {
        var self = this;
        self.form = form;
        self.text = ko.observable();

        self.remove = function () {
            self.form.questions.remove(self);
        };
    };

    return module;
});
