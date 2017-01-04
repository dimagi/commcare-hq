/* global ko, _, $ */

hqDefine('app_manager/js/form_workflow.js', function() {
    'use strict';

    var FormWorkflow = function (options) {
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

        var formIds = _.pluck(self.forms,  'uniqueId');
        self.formLinks = ko.observableArray(_.map(_.filter(options.formLinks, function(link) {
            return _.contains(formIds, link.form_id);
        }), function(link) {
            return new FormWorkflow.FormLink(link.xpath, link.form_id, self, link.datums);
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
        FORM_NOT_FOUND: gettext('This form either no longer exists or has a different case type'),
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
        // Default to linking to first form that can be auto linked
        var default_choice = _.find(workflow.forms, function(form) { return form.autoLink }),
            formId = default_choice ? default_choice.uniqueId : null;
        this.formLinks.push(new FormWorkflow.FormLink('', formId, workflow));
    };

    FormWorkflow.prototype.onDestroyFormLink = function(formLink, event) {
        var workflow = this;

        workflow.formLinks.remove(formLink);
        workflow.$changeEl.trigger('change'); // Manually trigger change so Save button activates
    };

    FormWorkflow.prototype.displayUnknownForm = function(formLink) {
        if (_.contains(formLink.errors(), FormWorkflow.Errors.FORM_NOT_FOUND)) {
            return "Unknown form";
        }
    };

    FormWorkflow.Form = function(form) {
        this.name = form.name;
        this.uniqueId = form.unique_id;
        this.autoLink = form.auto_link;
    };

    FormWorkflow.FormDatum = function(formLink, datum) {
        var self = this;
        self.formLink = formLink;
        self.name = datum.name;
        self.caseType = datum.case_type || 'unknown';
        self.xpath = ko.observable(datum.xpath || '');
        self.xpath.extend({ rateLimit: 200 });  // 1 update per 200 milliseconds
        self.xpath.subscribe(function() {
            self.formLink.serializeDatums();
        });
    };

    FormWorkflow.FormLink = function(xpath, formId, workflow, datums) {
        var self = this;
        self.xpath = ko.observable(xpath);
        self.formId = ko.observable(formId);
        self.autoLink = ko.observable();
        self.forms = workflow.forms || [];
        self.datums = ko.observableArray();
        self.manualDatums = ko.observable(false);
        self.datumsFetched = ko.observable(false);
        self.serializedDatums = ko.observable('');

        self.get_form_by_id = function(form_id) {
            return _.find(self.forms, function(form){ return form.uniqueId === form_id; });
        };

        self.serializeDatums = function() {
            var jsonDatums = JSON.stringify(_.map(self.datums(), function (datum) {
                return {'name': datum.name, 'xpath': datum.xpath()};
            }));
            self.serializedDatums(jsonDatums);
        };

        self.datums.subscribe(function() {
            self.serializeDatums();
        });

        self.wrap_datums = function(data) {
            self.datumsFetched(true);
            return _.map(data, function(datum) {
                return new FormWorkflow.FormDatum(self, datum);
            });
        };

        self.enableManualDatums = function(){
            self.manualDatums(true);
        };

        self.disableManualDatums = function(){
            self.manualDatums(false);
            $('#form-workflow .workflow-change-trigger').trigger('change');
            self.datums.removeAll();
        };

       // initialize
        self.autoLink(self.get_form_by_id(self.formId()).autoLink);
        self.datums(self.wrap_datums(datums));
        self.manualDatums(self.datums().length && self.autoLink());
        self.showLinkDatums = ko.computed(function(){
            return (!self.autoLink() || self.manualDatums());
        });

        self.formId.subscribe(function(form_id) {
            self.autoLink(self.get_form_by_id(form_id).autoLink);
            self.datumsFetched(false);
            self.datums([]);
            self.serializedDatums('');
        });

        self.fetchDatums = function() {
            $.get(
                workflow.formDatumsUrl,
                {form_id: self.formId()},
                function (data) {
                    self.datums(self.wrap_datums(data));
                },
                "json"
            );
        };

        self.errors = ko.computed(function() {
            var found,
                errors = [];

            found = _.find(self.forms, function(f) {
                return self.formId() === f.uniqueId;
            });

            if (!found) {
                errors.push(FormWorkflow.Errors.FORM_NOT_FOUND);
            }

            return errors;
        });
    };
    return {FormWorkflow: FormWorkflow};
});
