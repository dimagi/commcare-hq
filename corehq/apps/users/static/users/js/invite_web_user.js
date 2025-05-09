import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import customDataFields from "users/js/custom_data_fields";
import "hqwebapp/js/bootstrap3/validators.ko";
import "locations/js/widgets";

var inviteWebUserFormHandler = function () {
    var self = {},
        emailDefaultValue = $('#id_email').val();

    self.email = ko.observable()
        .extend({
            required: {
                message: gettext("Please specify an email."),
                params: true,
            },
            emailRFC2822: true,
        });

    self.showIdentityProviderMessage = ko.observable(false);
    self.identityProviderName = ko.observable('');
    self.trustedEmailDomain = ko.observable('');

    self.emailDelayed = ko.pureComputed(self.email)
        .extend({
            rateLimit: {
                method: "notifyWhenChangesStop",
                timeout: 400,
            },
            validation: {
                async: true,
                validator: function (val, params, callback) {
                    if (self.email.isValid()) {
                        self.showIdentityProviderMessage(false);

                        $.post(initialPageData.reverse('check_sso_trust'), {
                            username: self.email(),
                        }, function (result) {
                            self.showIdentityProviderMessage(!result.is_trusted);
                            self.identityProviderName(result.idp_name || '');
                            self.trustedEmailDomain(result.email_domain || '');
                            callback({ isValid: true });
                        });
                    }
                },
            },
        });

    self.isEmailValidating = ko.observable(false);
    self.emailDelayed.isValidating.subscribe(function (isValidating) {
        self.isEmailValidating(isValidating && self.email.isValid());
    });

    if (emailDefaultValue) {
        // we set the default here after the validators have been set up
        self.email(emailDefaultValue);
    }

    self.isSubmitEnabled = ko.computed(function () {
        return self.email.isValid()
            && self.emailDelayed.isValid()
            && !self.emailDelayed.isValidating();
    });
    var $customDataFieldsForm = $(".custom-data-fieldset");
    if ($customDataFieldsForm.length) {
        self.custom_fields = customDataFields.customDataFieldsEditor({
            profiles: initialPageData.get('custom_fields_profiles'),
            profile_slug: initialPageData.get('custom_fields_profile_slug'),
            slugs: initialPageData.get('custom_fields_slugs'),
            can_edit_original_profile: true,
            user_data: initialPageData.get('user_data'),
        });
    }

    return self;
};

$(function () {
    var formHandler = inviteWebUserFormHandler();
    $('#invite-web-user-form').koApplyBindings(formHandler);
});
