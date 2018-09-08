hqDefine("reports/js/filters/phone_number", ['knockout'], function (ko) {
    var phoneNumberFilterViewModel = function (initialValue, groups) {
        var PHONE_NUMBER_SELECT_OPTIONS =
            [
                { id: "has_phone_number", text: gettext("That have phone numbers") },
                { id: "no_phone_number", text: gettext("That do not have phone numbers") },
            ],
            model = {};

        model.filter_type = ko.observable(initialValue.filter_type || 'phone_number');
        model.phone_number_filter = ko.observable(initialValue.phone_number_filter);
        model.has_phone_number = ko.observable(initialValue.has_phone_number);
        model.contact_type = ko.observable(initialValue.contact_type);
        model.groups = ko.observableArray(groups);
        model.selected_group = ko.observable(initialValue.selected_group);
        model.verification_status = ko.observable(initialValue.verification_status);

        model.phone_number_options = ko.pureComputed(function () {
            if (model.contact_type() === 'cases') {
                return [PHONE_NUMBER_SELECT_OPTIONS[0]];
            }
            return PHONE_NUMBER_SELECT_OPTIONS;
        });

        model.show_phone_filter = ko.pureComputed(function () {
            return model.filter_type() === 'phone_number';
        });

        model.show_contact_filter = ko.pureComputed(function () {
            return model.filter_type() === 'contact';
        });

        model.show_group_filter = ko.pureComputed(function () {
            return model.show_contact_filter() && model.contact_type() === 'users';
        });

        model.can_edit_has_phone_number = ko.pureComputed(function () {
            return model.show_contact_filter() && model.contact_type() === 'cases';
        });

        model.show_verification_filter = ko.pureComputed(function () {
            return model.show_contact_filter() && model.has_phone_number() === 'has_phone_number';
        });

        return model;
    };

    return {
        model: phoneNumberFilterViewModel,
    };
});
