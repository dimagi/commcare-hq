
hqDefine('analytix/js/cta_forms', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/bootstrap3/validators.ko',        // needed for validation of startDate and endDate
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties,
) {
    let hubspotCtaForm = function (config) {
        let self = {};
        assertProperties.assertRequired(config, [
            'hubspotFormId',
            'showPreferredLanguage',
            'nextButtonText',
            'submitCallbackFn',
        ]);

        self.showPreferredLanguage = ko.observable(config.showPreferredLanguage);

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

        self.language = ko.observable();

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

        self.isLanguageFieldValid = ko.computed(function () {
            return !self.showPreferredLanguage() || !!self.language();
        });

        self.isFormReadyToSubmit = ko.computed(function () {
            return self.areMainFieldsValid() && self.isLanguageFieldValid();
        });

        self.isSubmitDisabled = ko.computed(function () {
            return !self.isFormReadyToSubmit();
        });

        self.errorMessage = ko.observable();
        self.showErrorMessage = ko.computed(function () {
            return !!self.errorMessage();
        });

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
            if (self.showPreferredLanguage()) {
                submitData.preferred_language = self.language();
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
