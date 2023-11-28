hqDefine('analytix/js/cta_forms', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/bootstrap3/validators.ko',        // needed for validation of startDate and endDate
    'intl-tel-input/build/js/intlTelInput.min',
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties
) {
    'use strict';

    let hubspotCtaForm = function (config) {
        let self = {};
        assertProperties.assertRequired(config, [
            'hubspotFormId',
            'showContactMethod',
            'showPreferredLanguage',
            'useWhatsApp',
            'useGoogleHangouts',
            'nextButtonText',
            'phoneNumberSelector',
            'submitCallbackFn',
        ]);

        self.showContactMethod = ko.observable(config.showContactMethod);
        self.showPreferredLanguage = ko.observable(config.showPreferredLanguage);

        self.useWhatsApp = ko.observable(config.useWhatsApp);
        self.useGoogleHangouts = ko.observable(config.useGoogleHangouts);
        self.nextButtonText = ko.observable(config.nextButtonText);

        self.firstname = ko.observable()
            .extend({
                required: {
                    message: gettext("Please enter your first name."),
                    params: true,
                },
            });
        self.lastname = ko.observable()
            .extend({
                required: {
                    message: gettext("Please enter your last name."),
                    params: true,
                },
            });
        self.company = ko.observable()
            .extend({
                required: {
                    message: gettext("Please enter your organization."),
                    params: true,
                },
            });
        self.email = ko.observable()
            .extend({
                required: {
                    message: gettext("Please enter your email address."),
                    params: true,
                },
            })
            .extend({
                emailRFC2822: true,
            });

        self.preferred_method_of_contact = ko.observable();

        self.phone = ko.observable();

        self.skype__c = ko.observable();
        self.preferred_whatsapp_number = ko.observable();

        self.showPhoneNumber = ko.computed(function () {
            return self.preferred_method_of_contact() === "Phone";
        });
        self.showSkype = ko.computed(function () {
            return self.preferred_method_of_contact() === "Skype";
        });
        self.showWhatsApp = ko.computed(function () {
            return self.preferred_method_of_contact() === "WhatsApp";
        });

        self.language__c = ko.observable();

        self.areMainFieldsValid = ko.computed(function () {
            return _.every([
                self.firstname,
                self.lastname,
                self.company,
                self.email,
            ], function (prop) {
                return prop() !== undefined && prop.isValid();
            });
        });

        self.areContactFieldsValid = ko.computed(function () {
            if (!self.showContactMethod()) {
                return true;
            }
            if (!self.preferred_method_of_contact()) {
                return false;
            }
            let isWhatsAppValid = self.showWhatsApp() && !!self.preferred_whatsapp_number(),
                isPhoneValid = self.showPhoneNumber() && !!self.phone(),
                isSkypeValid = self.showSkype() && !!self.skype__c();
            return isWhatsAppValid || isPhoneValid || isSkypeValid;
        });

        self.isLanguageFieldValid = ko.computed(function () {
            return !self.showPreferredLanguage() || !!self.language__c();
        });

        self.isFormReadyToSubmit = ko.computed(function () {
            return self.areContactFieldsValid() && self.areMainFieldsValid() && self.isLanguageFieldValid();
        });

        self.isSubmitDisabled = ko.computed(function () {
            return !self.isFormReadyToSubmit();
        });

        self.errorMessage = ko.observable();
        self.showErrorMessage = ko.computed(function () {
            return !!self.errorMessage();
        });

        config.phoneNumberSelector.intlTelInput({
            separateDialCode: true,
            utilsScript: initialPageData.get('number_utils_script'),
            initialCountry: "auto",
            geoIpLookup: function (success) {
                $.get("https://ipinfo.io", function () {}, "jsonp").always(function (resp) {
                    var countryCode = (resp && resp.country) ? resp.country : "";
                    if (!countryCode) {
                        countryCode = "us";
                    }
                    success(countryCode);
                });
            },
        });

        self.getFullPhoneNumber = function () {
            return config.phoneNumberSelector.intlTelInput("getNumber");
        };

        self.submitForm = function () {
            let submitData = {
                hubspot_form_id: config.hubspotFormId,
                firstname: self.firstname(),
                lastname: self.lastname(),
                company: self.company(),
                email: self.email(),

                // needed for hubspot context
                page_url: window.location.href,
                page_name: document.title,
            };
            if (self.showContactMethod()) {
                submitData.preferred_method_of_contact = self.preferred_method_of_contact();
            }
            if (self.showPhoneNumber()) {
                submitData.phone = self.phone();
            }
            if (self.showWhatsApp()) {
                submitData.preferred_whatsapp_number = self.preferred_whatsapp_number();
            }
            if (self.showSkype()) {
                submitData.skype__c = self.skype__c();
            }
            if (self.showPreferredLanguage()) {
                submitData.language__c = self.language__c();
            }
            $.ajax({
                method: 'post',
                url: initialPageData.reverse("submit_hubspot_cta_form"),
                data: submitData,
                dataType: 'json',
                success: function (data) {
                    if (data.success) {
                        config.submitCallbackFn();
                    } else {
                        self.errorMessage(data.message);
                    }
                },
            }).fail(function () {
                self.errorMessage(gettext("We are sorry, but something unexpected has occurred."));
            });
        };
        return self;


    };

    return {
        hubspotCtaForm: hubspotCtaForm,
    };
});
