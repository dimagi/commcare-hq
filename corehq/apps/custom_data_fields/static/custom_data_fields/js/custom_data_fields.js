hqDefine('custom_data_fields/js/custom_data_fields', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'hqwebapp/js/knockout_bindings.ko',     // needed for sortable binding
], function (
    $,
    ko,
    _,
    initialPageData,
    toggles
) {
    function Choice(choice) {
        var self = this;
        self.value = ko.observable(choice);
    }

    function CustomDataField() {
        var self = this;
        self.slug = ko.observable();
        self.label = ko.observable();
        self.is_required = ko.observable();
        self.choices = ko.observableArray();
        self.validationMode = ko.observable(); // 'choice' or 'regex'
        self.multiple_choice = ko.observable();
        self.regex = ko.observable();
        self.regex_msg = ko.observable();

        if (!toggles.toggleEnabled('REGEX_FIELD_VALIDATION')) {
            // if toggle isn't enabled - always show "choice" option
            self.validationMode('choice');
        }

        self.addChoice = function () {
            self.choices.unshift(new Choice());
        };

        self.removeChoice = function (choice) {
            self.choices.remove(choice);
        };

        self.init = function (field) {
            self.slug(field.slug);
            self.label(field.label);
            self.is_required(field.is_required);
            if (field.choices.length > 0) {
                self.validationMode('choice');
                self.choices(field.choices.map(function (choice) {
                    return new Choice(choice);
                }));
            } else if (field.regex) {
                self.validationMode('regex');
                self.regex(field.regex);
                self.regex_msg(field.regex_msg);
            }
            self.multiple_choice(field.is_multiple_choice);
        };

        self.serialize = function () {
            var choices = [],
                is_multiple_choice = null,
                regex = null,
                regex_msg = null;
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
                is_multiple_choice = self.multiple_choice();
            } else if (self.validationMode() === 'regex') {
                regex = self.regex();
                regex_msg = self.regex_msg();
            }

            return {
                'slug': self.slug(),
                'label': self.label(),
                'is_required': self.is_required(),
                'choices': choices,
                'regex': regex,
                'regex_msg': regex_msg,
                'is_multiple_choice': is_multiple_choice,
            };
        };
    }

    function CustomDataFieldsModel() {
        var self = this;
        self.data_fields = ko.observableArray();
        self.purge_existing = ko.observable(false);
        // The data field that the "remove field modal" currently refers to.
        self.modalField = ko.observable();

        self.addField = function () {
            self.data_fields.push(new CustomDataField());
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

        self.init = function (initialFields) {
            _.each(initialFields, function (field) {
                var custom_field = new CustomDataField();
                custom_field.init(field);
                self.data_fields.push(custom_field);
                custom_field.choices.subscribe(function () {
                    $("#save-custom-fields").prop("disabled", false);
                });
            });
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
    }

    $(function () {
        var customDataFieldsModel = new CustomDataFieldsModel();
        customDataFieldsModel.init(initialPageData.get('custom_fields'));
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
