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

        self.recordNameText = ko.observable("Name");
        self.questions = ko.observableArray();

        self.removeForm = function () {
            self.container.workflow.app.removeForm(self);
        };

        self.addQuestion = function () {
            self.questions.push(new Question(self));
        };

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
