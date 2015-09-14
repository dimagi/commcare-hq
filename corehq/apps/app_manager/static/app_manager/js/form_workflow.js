/* global ko, _, $ */

(function() {
    'use strict';

    window.FormWorkflow = function(options) {
        var self = this;

        self.formDatumsUrl = options.formDatumsUrl;

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
            return new FormWorkflow.FormLink(link.xpath, link.form_id, self);
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
        var default_choice = workflow.forms.length ? workflow.forms[0] : null,
            formId = default_choice ? default_choice.uniqueId : null,
            auto_link = default_choice ? default_choice.autoLink : null;
        this.formLinks.push(new FormWorkflow.FormLink('', formId, auto_link, workflow));
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
    };

    FormWorkflow.Form = function(form) {
        this.name = form.name;
        this.uniqueId = form.unique_id;
        this.autoLink = form.auto_link;
    };

    FormWorkflow.FormDatum = function(datum) {
        this.name = datum.name;
        this.caseType = datum.case_type || 'unknown';
        this.xpath = ko.observable('');
    };

    FormWorkflow.FormLink = function(xpath, formId, autoLink, workflow) {
        var self = this;
        self.xpath = ko.observable(xpath);
        self.formId = ko.observable(formId);
        self.autoLink = ko.observable(autoLink);
        self.forms = workflow.forms || [];
        self.datums = ko.observableArray();
        self.datumsFetched = ko.observable(false);

        self.get_form_by_id = function(form_id) {
            return _.find(self.forms, function(form){ return form.uniqueId === form_id; })
        };

        self.formId.subscribe(function(form_id) {
            self.autoLink(self.get_form_by_id(form_id).autoLink);
            self.datumsFetched(false);
            self.datums([]);
        });

        self.fetchDatums = function() {
            $.get(
                workflow.formDatumsUrl,
                {form_id: self.formId()},
                function (data) {
                    self.datumsFetched(true);
                    self.datums(_.map(data, function(datum) {
                        return new FormWorkflow.FormDatum(datum);
                    }))
                },
                "json"
            )
        };

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
