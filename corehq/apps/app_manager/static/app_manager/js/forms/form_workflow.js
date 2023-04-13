hqDefine('app_manager/js/forms/form_workflow', function () {
    'use strict';

    var FormWorkflow = function (options) {
        var self = this;

        self.formDatumsUrl = options.formDatumsUrl;

        // Human readable labels for the workflow types
        self.labels = options.labels;

        // Workflow type. See FormWorkflow.Values for available types
        self.workflow = ko.observable(options.workflow);

        self.workflowfallback = ko.observable(options.workflow_fallback);
        self.hasError = ko.observable(self.workflow() === FormWorkflow.Values.ERROR);
        self.hasWarning = ko.computed(function () {
            return !self.hasError()
                && hqImport("hqwebapp/js/initial_page_data").get("is_case_list_form")
                && self.workflow() !== FormWorkflow.Values.DEFAULT;
        });

        self.workflow.subscribe(function (value) {
            self.showFormLinkUI(value === FormWorkflow.Values.FORM);
            self.hasError(value === FormWorkflow.Values.ERROR);
        });

        // Element used to trigger a change when form link is removed
        self.$changeEl = options.$changeEl || $('#form-workflow .workflow-change-trigger');

        /* Form linking */
        self.showFormLinkUI = ko.observable(self.workflow() === FormWorkflow.Values.FORM);
        self.forms = _.map(options.forms, function (f) {
            return new FormWorkflow.Form(f);
        });

        // If original value isn't recognized, display an error
        if (!self.labels[self.workflow()]) {
            self.workflow(FormWorkflow.Values.ERROR);
        }

        var uniqueIds = _.pluck(self.forms,  'uniqueId');
        self.formLinks = ko.observableArray(_.map(_.filter(options.formLinks, function (link) {
            return uniqueIds.indexOf(link.uniqueId) >= 0;
        }), function (link) {
            return new FormWorkflow.FormLink(
                link.xpath,
                link.uniqueId,
                self,
                link.datums
            );
        }));
    };

    FormWorkflow.Values = {
        DEFAULT: 'default',
        ROOT: 'root',
        FORM: 'form',
        ERROR: 'error',
    };

    FormWorkflow.Errors = {
        FORM_NOT_FOUND: gettext('This form either no longer exists or has a different case type'),
    };


    FormWorkflow.prototype.workflowOptions = function () {
        var options = _.map(this.labels, function (label, value) {
            return {
                value: value,
                label: (value === FormWorkflow.Values.DEFAULT ? '* ' + label : label),
            };
        });
        if (this.hasError()) {
            options = options.concat({
                value: FormWorkflow.Values.ERROR,
                label: gettext("Unrecognized value"),
            });
        }
        return options;
    };

    FormWorkflow.prototype.workflowFallbackOptions = function () {
        // allow all options as fallback except the one for form linking
        var fallback_options = _.omit(this.labels, function (key, value) { return value === FormWorkflow.Values.FORM; });
        var options = _.map(fallback_options, function (label, value) {
            return {
                value: value,
                label: (value === FormWorkflow.Values.DEFAULT ? '* ' + label : label),
            };
        });
        if (this.hasError()) {
            options = options.concat({
                value: FormWorkflow.Values.ERROR,
                label: gettext("Unrecognized value"),
            });
        }
        return options;
    };

    FormWorkflow.prototype.onAddFormLink = function (workflow, event) {
        // Default to linking to first form that can be auto linked
        var default_choice = _.find(workflow.forms, function (form) { return form.autoLink; }),
            formId = default_choice ? default_choice.uniqueId : null;
        this.formLinks.push(new FormWorkflow.FormLink('', formId, workflow));
    };

    FormWorkflow.prototype.onDestroyFormLink = function (formLink, event) {
        var workflow = this;

        workflow.formLinks.remove(formLink);
        workflow.$changeEl.trigger('change'); // Manually trigger change so Save button activates
    };

    FormWorkflow.prototype.displayUnknownForm = function (formLink) {
        if (_.contains(formLink.errors(), FormWorkflow.Errors.FORM_NOT_FOUND)) {
            return "Unknown form";
        }
    };

    FormWorkflow.Form = function (form) {
        this.name = (form.auto_link ? "* " : "") + form.name;
        this.uniqueId = form.unique_id;
        this.autoLink = form.auto_link;
        this.allowManualLinking = form.allow_manual_linking;
    };

    FormWorkflow.FormDatum = function (formLink, datum) {
        var self = this;
        self.formLink = formLink;
        self.name = datum.name;
        self.caseType = datum.case_type || 'unknown';
        self.xpath = ko.observable(datum.xpath || '');
        self.xpath.extend({ rateLimit: 200 });  // 1 update per 200 milliseconds
        self.xpath.subscribe(function () {
            self.formLink.serializeDatums();
        });
    };

    FormWorkflow.FormLink = function (xpath, formId, workflow, datums) {
        var self = this;
        self.xpath = ko.observable(xpath);
        self.formId = ko.observable(formId);
        self.autoLink = ko.observable();
        self.allowManualLinking = ko.observable();
        self.forms = workflow.forms || [];
        self.datums = ko.observableArray();
        self.manualDatums = ko.observable(false);
        self.datumsFetched = ko.observable(false);
        self.datumsError = ko.observable(false);
        self.serializedDatums = ko.observable('');

        self.get_form_by_id = function (form_id) {
            return _.find(self.forms, function (form) { return form.uniqueId === form_id; });
        };

        self.serializeDatums = function () {
            var jsonDatums = JSON.stringify(_.map(self.datums(), function (datum) {
                return {'name': datum.name, 'xpath': datum.xpath()};
            }));
            self.serializedDatums(jsonDatums);
        };

        self.datums.subscribe(function () {
            self.serializeDatums();
        });

        self.wrap_datums = function (data) {
            self.datumsFetched(true);
            return _.map(data, function (datum) {
                return new FormWorkflow.FormDatum(self, datum);
            });
        };

        self.enableManualDatums = function () {
            self.manualDatums(true);
        };

        self.disableManualDatums = function () {
            self.manualDatums(false);
            $('#form-workflow .workflow-change-trigger').trigger('change');
            self.datums.removeAll();
        };

        // initialize
        let form = self.get_form_by_id(self.formId());
        self.autoLink(form ? form.autoLink : false);
        self.allowManualLinking(form ? form.allowManualLinking : false);
        self.datums(self.wrap_datums(datums));
        self.manualDatums(self.datums().length && self.autoLink());
        self.showLinkDatums = ko.computed(function () {
            return (!self.autoLink() || self.manualDatums());
        });

        self.formId.subscribe(function (form_id) {
            let form = self.get_form_by_id(form_id);
            self.autoLink(form ? form.autoLink : false);
            self.allowManualLinking(form ? form.allowManualLinking : false);
            self.datumsFetched(false);
            self.datums([]);
            self.serializedDatums('');
        });

        self.fetchDatums = function () {
            $.get(
                workflow.formDatumsUrl,
                {form_id: self.formId()},
                function (data) {
                    self.datums(self.wrap_datums(data));
                },
                "json"
            ).fail(function () {
                self.datumsFetched(false);
                self.datumsError(true);
            });
        };

        self.errors = ko.computed(function () {
            var found,
                errors = [];

            found = _.find(self.forms, function (f) {
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
