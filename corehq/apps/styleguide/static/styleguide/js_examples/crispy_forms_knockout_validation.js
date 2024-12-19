$(function () {
    'use strict';

    let UserModel = function () {
        let self = {},
            _rateLimit = {
                rateLimit: {
                    method: "notifyWhenChangesStop",
                    timeout: 400,
                },
            },
            // This line below would be part of an hqDefine import
            initialPageData = hqImport("hqwebapp/js/initial_page_data");

        self.username = ko.observable()
            .extend(_rateLimit)
            .extend({
                // It's possible to stack validators like this:
                required: {
                    message: gettext("Please specify a username."),
                    params: true,
                },
                minLength: {
                    message: gettext("Username must be at least three characters long."),
                    params: 3,
                },
            })
            .extend({
                validation: {
                    async: true,
                    validator: function (val, params, callback) {
                        // Order matters when specifying validators. This check only uses the previous two validators to calculate isValid()
                        if (self.username.isValid()) {
                            $.post(initialPageData.reverse('styleguide_validate_ko_demo'), {
                                username: self.username(),
                            }, function (result) {
                                callback({
                                    isValid: result.isValid,
                                    message: result.message,
                                });
                            });
                        }
                    },
                },
            });

        self.password = ko.observable()
            .extend(_rateLimit)
            .extend({
                required: {
                    message: gettext("Please specify a password."),
                    params: true,
                },
                minimumPasswordLength: {
                    params: 6,
                    message: gettext("Your password must be at least 6 characters long"),
                },
            });

        self.email = ko.observable()
            .extend({
                required: {
                    message: gettext("Please specify an email."),
                    params: true,
                },
                emailRFC2822: true,
            });

        // The async validation for email is decoupled in the emailDelayed here. Notice the difference in response between validating email vs username.
        // Being able to rate limit server-side calls is **extremely important** in a production environment to prevent unnecessary calls to the server.
        self.emailDelayed = ko.pureComputed(self.email)
            .extend(_rateLimit)
            .extend({
                validation: {
                    async: true,
                    validator: function (val, params, callback) {
                        if (self.email.isValid()) {
                            $.post(initialPageData.reverse('styleguide_validate_ko_demo'), {
                                email: self.email(),
                            }, function (result) {
                                callback({
                                    isValid: result.isValid,
                                    message: result.message,
                                });
                            });
                        }
                    },
                },
            });

        return self;
    };

    let ExampleFormModel = function () {
        let self = {};

        // newUser exists as a separate model so that it's easier to reset validation in _resetForm() below
        self.newUser = ko.observable(UserModel());

        self.isFormValid = ko.computed(function () {
            // When performing form validation ensure that async validators are not in isValidating states. If using delayed validators, ensure their states are also checked.
            return  (self.newUser().username.isValid()
                && !self.newUser().username.isValidating()
                && self.newUser().password.isValid()
                && self.newUser().email.isValid()
                && self.newUser().emailDelayed.isValid()
                && !self.newUser().emailDelayed.isValidating());
        });

        self.disableSubmit = ko.computed(function () {
            return !self.isFormValid();
        });

        self.alertText = ko.observable();

        self.onFormSubmit = function () {
            // an ajax call would likely happen here in the real world

            self.alertText("Thank you! '" + self.newUser().username() + "' has been created.");
            self._resetForm();
        };

        self.cancelSubmission = function () {
            self.alertText(gettext("Resetting form..."));
            self._resetForm();
        };

        self._resetForm = function () {
            self.newUser(UserModel());

            // clear alert text after 2 sec
            setTimeout(function () {
                self.alertText('');
            }, 2000);
        };
        return self;
    };
    $("#ko-validation-example").koApplyBindings(ExampleFormModel());
});
