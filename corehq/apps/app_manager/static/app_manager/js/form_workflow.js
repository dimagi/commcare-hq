/* global ko, _, $ */

(function() {
    'use strict';

    window.FormWorkflow = function(options) {
        var self = this;

        // Human readable labels for the workflow types
        self.labels = options.labels;

        // Workflow type. See FormWorkflow.Values for available types
        self.workflow = ko.observable(options.workflow);

        self.workflow.subscribe(function(value) {
            self.showFormLinkUI(value === FormWorkflow.Values.FORM);
        });


        // Element used to trigger a change when form link is removed
        self.$changeEl = options.$changeEl || $('#form-workflow .workflow-change-trigger');

        self.workflowDisplay = ko.computed(function() {
            return self.labels[self.workflow()];
        });

        /* Form linking */
        self.showFormLinkUI = ko.observable(self.workflow() === FormWorkflow.Values.FORM);
        self.forms = _.map(options.forms, function(f) {
            return new FormWorkflow.Form(f);
        });
        self.formLinks = ko.observableArray(_.map(options.formLinks, function(link) {
            return new FormWorkflow.FormLink(link.xpath, link.form_id, self.forms);
        }));
    };

    FormWorkflow.Values = {
        DEFAULT: 'default',
        ROOT: 'root',
        PARENT_MODULE: 'parent_module',
        MODULE: 'module',
        PREVIOUS_SCREEN: 'previous_screen',
        FORM: 'form',
    };

    FormWorkflow.Errors = {
        FORM_NOTFOUND: 'This form either no longer exists or has a different case type',
    };


    FormWorkflow.prototype.workflowOptions = function() {
        return _.map(this.labels, function(label, value) {
            return {
                value: value,
                label: (value === FormWorkflow.Values.DEFAULT ? '* ' + label : label)
            };
        });
    };

    FormWorkflow.prototype.onAddFormLink = function(workflow, event) {
        // Default to linking to first form
        var formId = workflow.forms.length ? workflow.forms[0].uniqueId : null;
        this.formLinks.push(new FormWorkflow.FormLink('', formId, workflow.forms));
    };

    FormWorkflow.prototype.onDestroyFormLink = function(formLink, event) {
        var workflow = this;

        workflow.formLinks.remove(formLink);
        workflow.$changeEl.trigger('change'); // Manually trigger change so Save button activates
    };

    FormWorkflow.prototype.displayUnknownForm = function(formLink) {
        if (_.contains(formLink.errors(), FormWorkflow.Errors.FORM_NOTFOUND)) {
            return "Unknown form";
        }
        return;
    };

    FormWorkflow.Form = function(form) {
        this.name = form.name;
        this.uniqueId = form.unique_id;
    };

    FormWorkflow.FormLink = function(xpath, formId, forms) {
        var self = this;
        self.xpath = ko.observable(xpath);
        self.formId = ko.observable(formId);
        self.forms = forms || [];

        self.errors = ko.computed(function() {
            var found,
                errors = [];

            found = _.find(self.forms, function(f) {
                return self.formId() === f.uniqueId;
            });

            if (!found) {
                errors.push(FormWorkflow.Errors.FORM_NOTFOUND);
            }

            return errors;
        });
    };
})();
