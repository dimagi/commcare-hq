hqDefine("sms/js/phone_number_filter", function() {
    function SMSPhoneNumberFilterViewModel(initial_value, groups) {
        var PHONE_NUMBER_SELECT_OPTIONS = [
                {id: "has_phone_number", text: gettext("That have phone numbers")},
                {id: "no_phone_number", text: gettext("That do not have phone numbers")},
            ],
            model = this;

        this.filter_type = ko.observable(initial_value.filter_type || 'phone_number');
        this.phone_number_filter = ko.observable(initial_value.phone_number_filter);
        this.has_phone_number = ko.observable(initial_value.has_phone_number);
        this.contact_type = ko.observable(initial_value.contact_type);
        this.groups = ko.observableArray(groups);
        this.selected_group = ko.observable(initial_value.selected_group);
        this.verification_status = ko.observable(initial_value.verification_status);

        this.phone_number_options = ko.pureComputed(function () {
            if (model.contact_type() === 'cases') {
                return [PHONE_NUMBER_SELECT_OPTIONS[0]];
            }
            return PHONE_NUMBER_SELECT_OPTIONS;
        });

        this.show_phone_filter = ko.pureComputed(function () {
            return model.filter_type() === 'phone_number';
        });

        this.show_contact_filter = ko.pureComputed(function () {
            return model.filter_type() === 'contact';
        });

        this.show_group_filter = ko.pureComputed(function () {
            return model.show_contact_filter() && model.contact_type() === 'users';
        });

        this.can_edit_has_phone_number = ko.pureComputed(function () {
            return model.show_contact_filter() && model.contact_type() === 'cases';
        });

        this.show_verification_filter = ko.pureComputed(function () {
            return model.show_contact_filter() && model.has_phone_number() === 'has_phone_number';
        });
    }

    var initial_value = {{ initial_value| JSON }},
        model = new SMSPhoneNumberFilterViewModel(initial_value, {{ groups| JSON }});
    $('#{{ css_id }}').koApplyBindings(model);
    $('[name=selected_group]').select2({
        allowClear: true,
        placeholder: '{% trans "Select a group" %}',
    });
});
