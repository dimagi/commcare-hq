/* global ko, _, $ */

(function() {
    'use strict';

    window.FormWorkflow = function(options) {
        var self = this;

        // Human readable labels for the workflow types
        self.labels = options.labels;

        // Workflow type. See FormWorkflow.Values for available types
        self.workflow = ko.observable(options.workflow);

        self.locale = options.locale || 'en';

        // Element used to trigger a change when form link is removed
        self.$changeEl = options.$changeEl || $('#form-workflow .workflow-change-trigger');

        /* Form linking */
        self.showFormLinkUI = ko.observable(self.workflow() === FormWorkflow.Values.FORM);
        self.forms = _.map(options.forms, function(f) {
            return new FormWorkflow.Form(f, { locale: self.locale });
        });
        self.formLinks = ko.observableArray(_.map(options.formLinks, function(link) {
            return new FormWorkflow.FormLink(link.xpath, link.form_id, { forms: self.forms });
        }));
    };

    FormWorkflow.Values = {
        DEFAULT: 'default',
        ROOT: 'root',
        MODULE: 'module',
        PREVIOUS_SCREEN: 'previous_screen',
        FORM: 'form',
    };

    FormWorkflow.Errors = {
        FORM_NOTFOUND: 'This form either no longer exists or has a different case type',
    };


    FormWorkflow.prototype.workflowDisplay = function() {
        return this.labels[this.workflow()];
    };

    FormWorkflow.prototype.workflowOptions = function() {
        return _.map(this.labels, function(label, value) {
            return {
                value: value,
                label: (value === FormWorkflow.Values.DEFAULT ? '* ' + label : label)
            };
        });
    };

    FormWorkflow.prototype.onWorkflowChange = function(workflow, event) {
        var value = $(event.currentTarget).val();

        this.showFormLinkUI(value === FormWorkflow.Values.FORM);
    };

    FormWorkflow.prototype.onAddFormLink = function(workflow, event) {
        this.formLinks.push(new FormWorkflow.FormLink());
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

    FormWorkflow.Form = function(form, options) {
        this.name = window.localize(form.name, options.locale);
        this.uniqueId = form.unique_id;
        this.locale = options.locale;
    };

    FormWorkflow.FormLink = function(xpath, formId, options) {
        var self = this;
        self.xpath = ko.observable(xpath);
        self.formId = ko.observable(formId);
        self.forms = options.forms || [];

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
