hqDefine('custom_data_fields/js/custom_data_fields', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/ui_elements/bootstrap3/ui-element-key-val-list',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko',     // needed for sortable and jqueryElement bindings
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData,
    uiElementKeyValueList
) {
    function Choice(choice) {
        var self = {};
        self.value = ko.observable(choice);
        return self;
    }

    function Field(options, parent) {
        assertProperties.assertRequired(options, [
            'slug',
            'label',
            'is_required',
            'choices',
            'regex',
            'regex_msg',
            'upstream_id',
        ]);
        var self = {};
        self.parent = parent;
        self.slug = ko.observable(options.slug);
        self.label = ko.observable(options.label);
        self.is_required = ko.observable(options.is_required);
        self.choices = ko.observableArray(options.choices.map(function (choice) {
            return Choice(choice);
        }));
        self.validationMode = ko.observable();
        if (options.choices.length) {
            self.validationMode('choice');
        } else if (options.regex) {
            self.validationMode('regex');
        }
        self.regex = ko.observable(options.regex);
        self.regex_msg = ko.observable(options.regex_msg);
        self.upstream_id = options.upstream_id;
        self.editIcon = ko.observable("fa-edit");

        self.isEditable = ko.pureComputed(function () {
            return !options.upstream_id || parent.unlockLinkedData();
        });

        self.hasModalDetail = true;
        self.modalName = ko.computed(function () {
            return self.label() || self.slug();
        });

        if (!initialPageData.get('can_view_regex_field_validation')) {
            // if toggle isn't enabled - always show "choice" option
            self.validationMode('choice');
        }

        self.addChoice = function () {
            self.choices.unshift(Choice());
        };

        self.removeChoice = function (choice) {
            self.choices.remove(choice);
        };

        self.startEditing = function () {
            self.isEditable(true);
        };

        self.deleteLink = ko.pureComputed(function () {
            return self.isEditable() ? '#delete-confirm-modal' : null;
        }, self);

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
                'upstream_id': self.upstream_id,
            };
        };

        return self;
    }

    function Profile(options, parent) {
        assertProperties.assertRequired(options, ['id', 'name', 'fields', 'upstream_id']);
        var self = {};
        self.parent = parent;

        self.id = ko.observable(options.id);
        self.name = ko.observable(options.name);
        self.upstream_id = options.upstream_id;
        self.serializedFields = ko.observable();

        self.hasModalDetail = false;
        self.modalName = ko.computed(function () {
            return self.name();
        });

        self.isEditable = ko.pureComputed(function () {
            return !self.upstream_id || self.parent.unlockLinkedData();
        });

        self.fields = uiElementKeyValueList.new(
            String(Math.random()).slice(2),
            gettext("Edit Profile")
        );
        self.fields.setEdit(self.isEditable());

        self.fields.on("change", function () {
            $(":submit").prop("disabled", false);
        });
        self.fields.val(options.fields);
        self.$fields = self.fields.ui;

        self.isEditable.subscribe(function (newValue) {
            // need to manually subscribe to changes here, because 'fields' is a jquery element
            self.fields.setEdit(newValue);
        });

        self.deleteLink = ko.pureComputed(function () {
            return self.isEditable() ? '#delete-confirm-modal' : null;
        }, self);

        self.serialize = function () {
            return {
                id: self.id(),
                name: self.name(),
                fields: self.fields.val(),
                upstream_id: self.upstream_id,
            };
        };

        return self;
    }

    function CustomDataFieldsModel(options) {
        assertProperties.assertRequired(options,
            [ 'custom_fields', 'custom_fields_profiles', 'can_edit_linked_data']);

        var self = {};
        self.data_fields = ko.observableArray();
        self.profiles = ko.observableArray();
        self.purge_existing = ko.observable(false);
        // The field  or profile that the removal modal currently refers to.
        self.modalModel = ko.observable();

        self.unlockLinkedData = ko.observable(false);

        self.toggleLinkedLock = function () {
            self.unlockLinkedData(!self.unlockLinkedData());
        };

        self.hasLinkedData = ko.pureComputed(function () {
            const hasLinkedFields = self.data_fields().some(field => field.upstream_id);
            if (hasLinkedFields) {
                return true;
            }

            // linked profiles can exist without linked fields if the user attempts to save
            // after the linked fields are removed.
            const hasLinkedProfiles = self.profiles().some(profile => profile.upstream_id);
            return hasLinkedProfiles;
        });

        self.allowEdit = options.can_edit_linked_data;

        self.addField = function () {
            self.data_fields.push(Field({
                slug: '',
                label: '',
                is_required: false,
                choices: [],
                regex: '',
                regex_msg: '',
                upstream_id: null,
            }, self));
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
                upstream_id: null,
            }, self));
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
            var customField = Field(field, self);
            self.data_fields.push(customField);
            customField.choices.subscribe(function () {
                $("#save-custom-fields").prop("disabled", false);
            });
            // NOTE: There must be a better way to do this.
            // The save button's state should likely be included and controlled by the view model
            customField.validationMode.subscribe(function () {
                $("#save-custom-fields").prop("disabled", false);
            });
        });
        _.each(options.custom_fields_profiles, function (profile) {
            self.profiles.push(Profile(profile, self));
        });

        return self;
    }

    $(function () {
        var customDataFieldsModel = CustomDataFieldsModel({
            custom_fields: initialPageData.get('custom_fields'),
            custom_fields_profiles: initialPageData.get('custom_fields_profiles'),
            can_edit_linked_data: initialPageData.get('can_edit_linked_data'),
        });
        customDataFieldsModel.data_fields.subscribe(function () {
            $("#save-custom-fields").prop("disabled", false);
        });
        customDataFieldsModel.profiles.subscribe(function () {
            $("#save-custom-fields").prop("disabled", false);
        });

        $('#custom-fields-form').koApplyBindings(customDataFieldsModel);
        $('#lock-container').koApplyBindings(customDataFieldsModel);

        $('form[id="custom-fields-form"]').on("change", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        }).on("input", null, null, function () {
            $("#save-custom-fields").prop("disabled", false);
        });
    });
});
