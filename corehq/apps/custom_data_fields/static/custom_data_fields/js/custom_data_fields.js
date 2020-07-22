hqDefine('custom_data_fields/js/custom_data_fields', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'hqwebapp/js/knockout_bindings.ko',     // needed for sortable binding
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData,
    toggles
) {
    function Choice(choice) {
        var self = {};
        self.value = ko.observable(choice);
        return self;
    }

    function Field(options) {
        assertProperties.assertRequired(options, [
            'slug',
            'label',
            'is_required',
            'choices',
            'regex',
            'regex_msg',
        ]);
        var self = {};
        self.slug = ko.observable(options.slug);
        self.label = ko.observable(options.label);
        self.is_required = ko.observable(options.is_required);
        self.choices = ko.observableArray(options.choices.map(function (choice) {
            return Choice(choice);
        }));
        self.validationMode = ko.observable(options.choices.length ? 'choice' : 'regex');
        self.regex = ko.observable(options.regex);
        self.regex_msg = ko.observable(options.regex_msg);

        if (!toggles.toggleEnabled('REGEX_FIELD_VALIDATION')) {
            // if toggle isn't enabled - always show "choice" option
            self.validationMode('choice');
        }

        self.addChoice = function () {
            self.choices.unshift(Choice());
        };

        self.removeChoice = function (choice) {
            self.choices.remove(choice);
        };

        self.serialize = function () {
            var choices = [],
                regex = null,
                regexMsg = null;
            if (self.validationMode() === 'choice') {
                var choicesToRemove = [];
                _.each(self.choices(), function (choice) {
                    if (choice.value()) {
                        choices.push(choice.value());
                    } else {
                        choicesToRemove.push(choice);
                    }
                });
                _.each(choicesToRemove, function (choice) {
                    self.removeChoice(choice);
                });
            } else if (self.validationMode() === 'regex') {
                regex = self.regex();
                regexMsg = self.regex_msg();
            }

            return {
                'slug': self.slug(),
                'label': self.label(),
                'is_required': self.is_required(),
                'choices': choices,
                'regex': regex,
                'regex_msg': regexMsg,
            };
        };

        return self;
    }

    function CustomDataFieldsModel(options) {
        assertProperties.assertRequired(options, ['custom_fields']);

        var self = {};
        self.data_fields = ko.observableArray();
        self.purge_existing = ko.observable(false);
        // The data field that the "remove field modal" currently refers to.
        self.modalField = ko.observable();

        self.addField = function () {
            self.data_fields.push(Field({
                slug: '',
                label: '',
                is_required: false,
                choices: [],
                regex: '',
                regex_msg: '',
            }));
        };

        self.removeField = function (field) {
            self.data_fields.remove(field);
        };

        self.setModalField = function (field) {
            self.modalField(field);
        };

        self.confirmRemoveField = function () {
            // Remove the field that the "remove field modal" currently refers to.
            self.removeField(self.modalField());
        };

        self.serialize = function () {
            var fields = [];
            var fieldsToRemove = [];
            _.each(self.data_fields(), function (field) {
                if (field.slug() || field.label()) {
                    fields.push(field.serialize());
                } else {
                    fieldsToRemove.push(field);
                }
            });

            _.each(fieldsToRemove, function (field) {
                self.removeField(field);
            });
            return fields;
        };

        self.submitFields = function (fieldsForm) {
            var customDataFieldsForm = $("<form>")
                .attr("method", "post")
                .attr("action", fieldsForm.action);


            $("<input type='hidden'>")
                .attr("name", 'csrfmiddlewaretoken')
                .attr("value", $("#csrfTokenContainer").val())
                .appendTo(customDataFieldsForm);

            $('<input type="hidden">')
                .attr('name', 'data_fields')
                .attr('value', JSON.stringify(self.serialize()))
                .appendTo(customDataFieldsForm);

            $('<input type="hidden">')
                .attr('name', 'purge_existing')
                .attr('value', self.purge_existing())
                .appendTo(customDataFieldsForm);
            customDataFieldsForm.appendTo("body");
            customDataFieldsForm.submit();
        };

        // Initialize
        _.each(options.custom_fields, function (field) {
            var customField = Field(field);
            self.data_fields.push(customField);
            customField.choices.subscribe(function () {
                $("#save-custom-fields").prop("disabled", false);
            });
        });

        return self;
    }

    $(function () {
        var customDataFieldsModel = CustomDataFieldsModel({
            custom_fields: initialPageData.get('custom_fields'),
        });
        customDataFieldsModel.data_fields.subscribe(function () {
            $("#save-custom-fields").prop("disabled", false);
        });

        $('#custom-fields-form').koApplyBindings(customDataFieldsModel);

        $('form[id="custom-fields-form"]').on("change", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        }).on("input", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        });

        $('.modal-footer button').on("click", function () {
            $(":submit").prop("disabled", false);
        });
    });
});
