/* global _ */
/* global $ */
/* global ko */

hqDefine('prototype.workflow_builder.forms', function () {
   'use strict';
    var module = {};
    var utils = hqImport('prototype.workflow_builder.utils');

    module.Form = function (
       container
    ) {
        var self = this;
        utils.BaseAppObj.call(self);
        self.container = container;
        self.order = ko.observable(0);

        self.updateOrder = function () {
            var $UI = $('#' + self.draggableId());
            self.order($UI.prevAll('.workflow-form').length);
        };

        self.recordNameText = ko.observable("What is the name?");
        self.records = ko.observableArray();
        self.questions = ko.observableArray();
        self.isSelected = ko.observable(false);

        self.removeForm = function () {
            self.container.workflow.app.removeForm(self);
        };

        self.addQuestion = function () {
            self.questions.push(new Question(self));
        };

        self.hasNoQuestions = ko.computed(function () {
            return self.questions().length === 0;
        });

        self.isRegForm = ko.observable(self.container.formType() === utils.FormType.REGISTRATION);
        self.isCompleteForm = ko.observable(self.container.formType() === utils.FormType.COMPLETION);

    };
    module.Form.prototype = Object.create(utils.BaseAppObj.prototype);
    
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
