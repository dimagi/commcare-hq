/* global $ */
/* global ko */
/* global _ */
/* global RMI */
/* global django */

/* New User Registration Form Model
 * This model is for validating and stepping through the new user registration form
 */

hqDefine('registration/js/new_user.ko', function () {
    'use strict';
    var module = {};

    var _private = {},
        _appcues = hqImport('analytix/js/appcues'),
        _kissmetrics = hqImport('analytix/js/kissmetrix');

    _private.rmiUrl = null;
    _private.csrf = null;
    _private.showPasswordFeedback = false;
    _private.rmi = function () {
        throw "Please call initRMI first.";
    };
    _private.resetEmailFeedback = function (isValidating) {
        throw "please call setResetEmailFeedbackFn. " +
              "Expects boolean isValidating. " + isValidating;
    };
    _private.submitAttemptAnalytics = function (data) {  // eslint-disable-line no-unused-vars
        _kissmetrics.track.event("Clicked Create Account");
    };
    _private.getPhoneNumberFn = function () {
        // number to return phone number
    };
    _private.submitSuccessAnalytics = function () {
        // analytics haven't loaded yet or at all, fail silently
    };

    // Can't set up analytics until the values for the A/B tests are ready
    _kissmetrics.whenReadyAlways(function () {
        _kissmetrics.track.event("Viewed CommCare signup page");

        _private.submitSuccessAnalytics = function (data) {
            _kissmetrics.track.event("Account Creation was Successful");

            var appcuesEvent = "Assigned user to Appcues test",
                appcuesData = {
                    'Appcues test': data.appcuesAbTest,
                };

            _appcues.identify(data.email, appcuesData);
            _appcues.trackEvent(appcuesEvent, appcuesData);

            _kissmetrics.identify(data.email);
            _kissmetrics.identifyTraits(appcuesData);
            _kissmetrics.track.event(appcuesEvent, appcuesData);

            if (data.deniedEmail) {
                _kissmetrics.track.event("Created account after previous denial due to enterprise restricting signups", {
                    email: data.email,
                    previousAttempt: data.deniedEmail,
                });
            }
        };
    });

    module.setResetEmailFeedbackFn = function (callback) {
        // use this function to reset the form-control-feedback ui
        // in the email form so that it removes the waiting / checking email note
        // or adds it if the validator is still in async validation mode
        _private.resetEmailFeedback = callback;
    };

    module.setSubmitAttemptFn = function (callback) {
        _private.submitAttemptFn = callback;
    };

    module.setGetPhoneNumberFn = function (callback) {
        _private.getPhoneNumberFn = callback;
    };

    module.initRMI = function (rmiUrl) {
        _private.rmiUrl = rmiUrl;
        _private.csrf = $("#csrfTokenContainer").val();

        _private.rmi = function (remoteMethod, data, options) {
            options = options || {};
            options.headers = {"DjNg-Remote-Method": remoteMethod};
            var _rmi = RMI(_private.rmiUrl, _private.csrf);
            return _rmi("", data, options);
        };
    };

    module.showPasswordFeedback = function () {
        _private.showPasswordFeedback = true;
    };

    module.onModuleLoad = function () {
        throw "overwrite onModule load to remove loading indicators";
    };

    module.formViewModel = function (defaults, containerSelector, steps) {
        var self = {};

        module.onModuleLoad();

        // add a short delay to some of the validators so that
        var _rateLimit = { rateLimit: { method: "notifyWhenChangesStop", timeout: 400 } };

        // ---------------------------------------------------------------------
        // Step 1 Fields
        // ---------------------------------------------------------------------
        self.fullName = ko.observable(defaults.full_name)
            .extend({
                required: {
                    message: django.gettext("Please enter your name."),
                    params: true,
                },
            });

        // ---------------------------------------------------------------------
        self.email = ko.observable()
            .extend({
                required: {
                    message: django.gettext("Please specify an email."),
                    params: true,
                },
            })
            .extend({
                emailRFC2822: true,
            });
        self.deniedEmail = ko.observable('');
        self.emailDelayed = ko.pureComputed(self.email)
            .extend(_rateLimit)
            .extend({
                validation: {
                    async: true,
                    validator: function (val, params, callback) {
                        if (self.email.isValid()) {
                            _private.rmi(
                                "check_username_availability",  // TODO: use new view
                                {email: val},
                                {
                                    success: function (result) {
                                        if (result.restrictedByDomain) {
                                            _kissmetrics.track.event("Denied account due to enterprise restricting signups", {email: val});
                                            self.deniedEmail(val);
                                        }
                                        callback({
                                            isValid: result.isValid,
                                            message: result.message,
                                        });
                                    },
                                }
                            );
                        } else if (self.email() !== undefined) {
                            _private.resetEmailFeedback(false);
                        }
                    },
                },
            });
        if (defaults.email) {
            // triggers validation check on pre-filled emails
            self.email(defaults.email);
        }
        self.isEmailValidating = ko.observable(false);
        self.validatingEmailMsg = ko.observable(django.gettext("Checking email..."));
        self.emailDelayed.isValidating.subscribe(function (isValidating) {
            self.isEmailValidating(isValidating && self.email.isValid());
            _private.resetEmailFeedback(isValidating);
        });

        // ---------------------------------------------------------------------
        self.password = ko.observable(defaults.password)
            .extend({
                required: {
                    message: django.gettext("Please specify a password."),
                    params: true,
                },
            });
        self.passwordDelayed = ko.pureComputed(self.password)
            .extend(_rateLimit)
            .extend({
                zxcvbnPassword: 2,
            });


        // --- Optional for test ----
        self.phoneNumber = ko.observable();

        // ---------------------------------------------------------------------
        // Step 2
        // ---------------------------------------------------------------------
        self.projectName = ko.observable(defaults.project_name)
            .extend({
                required: {
                    message: django.gettext("Please specify a project name."),
                    params: true,
                },
            });
        self.eulaConfirmed = ko.observable(defaults.eula_confirmed || false);
        self.eulaConfirmed.subscribe(function (isConfirmed) {
            if (isConfirmed && self.projectName() === undefined) {
                self.projectName('');
            }
        });

        // For User Persona Field
        self.hasPersonaFields = $(containerSelector).find("[name='persona']").length;
        self.personaChoice = ko.observable();
        self.personaOther = ko.observable()
            .extend({
                required: {
                    message: django.gettext("Please specify."),
                    params: true,
                },
            });
        self.isPersonaChoiceOther = ko.computed(function () {
            return self.personaChoice() === 'Other';
        });
        self.isPersonaChoiceChosen = ko.computed(function () {
            return !_.isEmpty(self.personaChoice());
        });
        self.isPersonaChoiceNeeded = ko.computed(function () {
            return self.eulaConfirmed() && !self.isPersonaChoiceChosen();
        });
        self.isPersonaChoiceOtherPresent = ko.computed(function () {
            return self.isPersonaChoiceOther() && self.personaOther();
        });
        self.isPersonaChoiceOtherNeeded = ko.computed(function () {
            return self.eulaConfirmed() && self.isPersonaChoiceOther() && !self.personaOther();
        });
        self.isPersonaValid = ko.computed(function () {
            if (!self.hasPersonaFields) {
                return true;
            }
            return self.isPersonaChoiceChosen()
                   && (!self.isPersonaChoiceOther() || self.isPersonaChoiceOtherPresent());
        });

        // ---------------------------------------------------------------------
        // Form Functionality
        // ---------------------------------------------------------------------
        self.steps = ko.observableArray(steps);
        self.currentStep = ko.observable(0);

        self.currentStep.subscribe(function (newValue) {
            if (newValue === 1) {
                _kissmetrics.track.event("Clicked Next button on Step 1 of CommCare signup");
            }
        });

        var _getDataForSubmission = function () {
            var password = self.password();
            if (hqImport("hqwebapp/js/initial_page_data").get("implement_password_obfuscation")) {
                password = (hqImport("nic_compliance/js/encoder")()).encode(self.password());
            }
            var data = {
                full_name: self.fullName(),
                email: self.email(),
                password: password,
                project_name: self.projectName(),
                eula_confirmed: self.eulaConfirmed(),
                phone_number: _private.getPhoneNumberFn() || self.phoneNumber(),
                atypical_user: defaults.atypical_user,
            };
            if (self.hasPersonaFields) {
                _.extend(data, {
                    persona: self.personaChoice(),
                    persona_other: self.isPersonaChoiceOther() ? self.personaOther() : '',
                });
            }
            return data;
        };

        var _getFormStepUi = function (stepNum) {
            return $(containerSelector + " form ." + self.steps()[stepNum]);
        };

        self.isStepOneValid = ko.computed(function () {
            return self.fullName() !== undefined
                && self.email() !== undefined
                && self.password() !== undefined
                && self.fullName.isValid()
                && self.email.isValid()
                && self.emailDelayed.isValid()
                && !self.emailDelayed.isValidating()
                && self.password.isValid()
                && self.passwordDelayed.isValid();
        });

        self.disableNextStepOne = ko.computed(function () {
            return !self.isStepOneValid();
        });

        self.isStepTwoValid = ko.computed(function () {
            return self.projectName() !== undefined
                && self.projectName.isValid()
                && self.isPersonaValid()
                && self.eulaConfirmed();
        });

        self.disableNextStepTwo = ko.computed(function () {
            return !self.isStepTwoValid();
        });

        self.nextStep = function () {
            var _nextStep = self.currentStep() + 1;
            if (_nextStep >= self.steps().length) {
                return;
            }
            _getFormStepUi(self.currentStep())
                .hide("slide", {}, 300, function () {
                    _getFormStepUi(_nextStep).fadeIn(500);
                    self.currentStep(_nextStep);
                });
        };

        self.previousStep = function () {
            var _prevStep = self.currentStep() - 1;
            if (_prevStep < 0) {
                return;
            }
            _getFormStepUi(self.currentStep())
                .hide("slide", {direction: "right"}, 300, function () {
                    _getFormStepUi(_prevStep).fadeIn(500);
                    self.currentStep(_prevStep);
                });
        };

        // ---------------------------------------------------------------------
        // Handling Form Submission & Submit Errors
        // ---------------------------------------------------------------------

        self.submitErrors = ko.observableArray();
        self.hasSubmitErrors = ko.computed(function () {
            return self.submitErrors().length;
        });
        self.isSubmitting = ko.observable(false);
        self.isSubmitSuccess = ko.observable(false);

        self.hasServerError = ko.observable(false);  // in the case of 500s

        // Fake timeouts to give the user some feeling of progress.
        self.showFirstTimeout = ko.observable(false);
        self.showSecondTimeout = ko.observable(false);
        self.showThirdTimeout = ko.observable(false);
        self.showFourthTimeout = ko.observable(false);

        self.submitForm = function () {
            self.showFirstTimeout(false);
            self.showSecondTimeout(false);
            self.showThirdTimeout(false);
            self.showFourthTimeout(false);

            // Fake timeouts to give the user some feeling of progress.
            // todo determine good timeout intervals based on avg time to set up new account
            setTimeout(function () {
                self.showFirstTimeout(true);
            }, 1000);
            setTimeout(function () {
                self.showSecondTimeout(true);
            }, 2000);
            setTimeout(function () {
                self.showThirdTimeout(true);
            }, 3000);
            setTimeout(function () {
                self.showFourthTimeout(true);
            }, 4000);

            self.submitErrors([]);
            self.isSubmitting(true);

            var submitData = _getDataForSubmission();
            _private.submitAttemptAnalytics(submitData);

            _private.rmi(
                "register_new_user",
                {data: submitData},
                {
                    success: function (response) {
                        if (response.errors !== undefined
                            && !_.isEmpty(response.errors)) {
                            self.isSubmitting(false);
                            _.each(response.errors, function (val, key) {
                                self.submitErrors.push({
                                    fieldName: key.replace('_', " "),
                                    errors: val.join(", "),
                                });
                            });
                        } else if (response.success) {
                            self.isSubmitting(false);
                            self.isSubmitSuccess(true);
                            _private.submitSuccessAnalytics(_.extend({}, submitData, {
                                email: self.email(),
                                deniedEmail: self.deniedEmail(),
                                appcuesAbTest: response.appcues_ab_test ? 'On' : 'Off',
                            }));
                        }
                    },
                    error: function () {
                        self.isSubmitting(false);
                        self.hasServerError(true);
                    },
                }
            );
            self.nextStep();
        };

        return self;
    };

    return module;
});
