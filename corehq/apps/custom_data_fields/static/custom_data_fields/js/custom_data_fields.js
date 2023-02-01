hqDefine('custom_data_fields/js/custom_data_fields', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'hqwebapp/js/ui_elements/ui-element-key-val-list',
    'hqwebapp/js/knockout_bindings.ko',     // needed for sortable and jqueryElement bindings
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData,
    toggles,
    uiElementKeyValueList
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

        self.hasModalDetail = true;
        self.modalName = ko.computed(function () {
            return self.label() || self.slug();
        });

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

    function Profile(options) {
        assertProperties.assertRequired(options, ['id', 'name', 'fields']);
        var self = {};

        self.id = ko.observable(options.id);
        self.name = ko.observable(options.name);
        self.serializedFields = ko.observable();

        self.hasModalDetail = false;
        self.modalName = ko.computed(function () {
            return self.name();
        });

        self.fields = uiElementKeyValueList.new(
            String(Math.random()).slice(2),
            gettext("Edit Profile")
        );
        self.fields.on("change", function () {
            $(":submit").prop("disabled", false);
        });
        self.fields.val(options.fields);
        self.$fields = self.fields.ui;

        self.serialize = function () {
            return {
                id: self.id(),
                name: self.name(),
                fields: self.fields.val(),
            };
        };

        return self;
    }

    function CustomDataFieldsModel(options) {
        assertProperties.assertRequired(options, ['custom_fields', 'custom_fields_profiles']);

        var self = {};
        self.data_fields = ko.observableArray();
        self.profiles = ko.observableArray();
        self.purge_existing = ko.observable(false);
        // The field  or profile that the removal modal currently refers to.
        self.modalModel = ko.observable();

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

        self.removeModel = function (model) {
            self.data_fields.remove(model);
            self.profiles.remove(model);
        };

        self.setModalModel = function (model) {
            self.modalModel(model);
        };

        self.confirmRemoveModel = function () {
            self.removeModel(self.modalModel());
        };

        self.addProfile = function () {
            self.profiles.push(Profile({
                id: '',
                name: '',
                fields: {},
            }));
        };

        self.serializeFields = function () {
            return _.map(self.data_fields(), function (field) {
                return field.serialize();
            });
        };

        self.serializeProfiles = function () {
            return _.map(self.profiles(), function (profile) {
                return profile.serialize();
            });
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
                .attr('value', JSON.stringify(self.serializeFields()))
                .appendTo(customDataFieldsForm);

            $('<input type="hidden">')
                .attr('name', 'profiles')
                .attr('value', JSON.stringify(self.serializeProfiles()))
                .appendTo(customDataFieldsForm);

            $('<input type="hidden">')
                .attr('name', 'purge_existing')
                .attr('value', self.purge_existing())
                .appendTo(customDataFieldsForm);

            $('<input type="hidden">')
                .attr('name', 'profiles_active')
                .attr('value', $('#custom-fields-form .nav-tabs li:last').hasClass('active'))
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
        _.each(options.custom_fields_profiles, function (profile) {
            self.profiles.push(Profile(profile));
        });

        return self;
    }

    $(function () {
        var customDataFieldsModel = CustomDataFieldsModel({
            custom_fields: initialPageData.get('custom_fields'),
            custom_fields_profiles: initialPageData.get('custom_fields_profiles'),
        });
        customDataFieldsModel.data_fields.subscribe(function () {
            $("#save-custom-fields").prop("disabled", false);
        });
        customDataFieldsModel.profiles.subscribe(function () {
            $("#save-custom-fields").prop("disabled", false);
        });

        $('#custom-fields-form').koApplyBindings(customDataFieldsModel);

        $('form[id="custom-fields-form"]').on("change", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        }).on("input", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        });
    });
});
