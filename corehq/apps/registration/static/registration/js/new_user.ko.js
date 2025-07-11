import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import RMI from "jquery.rmi/jquery.rmi";
import noopMetrics from "analytix/js/noopMetrics";
import initialPageData from "hqwebapp/js/initial_page_data";
import intlTelInput from "intl-tel-input/build/js/intlTelInput.min";
import serverLocationSelect from "registration/js/server_location_select";
import "jquery-ui/ui/effect";
import "jquery-ui/ui/effects/effect-slide";
import "jquery-ui-built-themes/redmond/jquery-ui.min.css";
import "hqwebapp/js/password_validators.ko";

var module = {};

module.rmiUrl = null;
module.csrf = null;
module.showPasswordFeedback = false;
module.rmi = function () {
    throw new Error("Please call initRMI first.");
};
module.resetEmailFeedback = function (isValidating) {
    throw new Error("please call setResetEmailFeedbackFn. " +
        "Expects boolean isValidating. " + isValidating);
};
module.submitAttemptAnalytics = function (data) {  // eslint-disable-line no-unused-vars
    noopMetrics.track.event("Clicked Create Account");
};
module.getPhoneNumberFn = function () {
    // number to return phone number
};
module.submitSuccessAnalytics = function () {
    // analytics haven't loaded yet or at all, fail silently
};

module.onModuleLoad = function () {
    throw new Error("overwrite onModule load to remove loading indicators");
};

var formViewModel = function (defaults, containerSelector, steps) {
    var self = {};

    module.onModuleLoad();

    // add a short delay to some of the validators so that
    var _rateLimit = { rateLimit: { method: "notifyWhenChangesStop", timeout: 400 } };

    // ---------------------------------------------------------------------
    // Step 1 Fields
    // ---------------------------------------------------------------------
    const serverLocationModel = serverLocationSelect.serverLocationModel({});
    self.serverLocation = serverLocationModel.serverLocation;
    self.fullName = ko.observable(defaults.full_name)
        .extend({
            required: {
                message: gettext("Please enter your name."),
                params: true,
            },
        });

    // ---------------------------------------------------------------------
    self.email = ko.observable()
        .extend({
            required: {
                message: gettext("Please specify an email."),
                params: true,
            },
        })
        .extend({
            emailRFC2822: true,
        });
    self.deniedEmail = ko.observable('');
    self.isSso = ko.observable(false);
    self.ssoMessage = ko.observable();
    self.showPasswordField = ko.computed(function () {
        return !self.isSso();
    });
    self.emailDelayed = ko.pureComputed(self.email)
        .extend(_rateLimit)
        .extend({
            validation: {
                async: true,
                validator: function (val, params, callback) {
                    if (self.email.isValid()) {
                        module.rmi(
                            "check_username_availability",
                            {email: val},
                            {
                                success: function (result) {
                                    if (result.restrictedByDomain) {
                                        noopMetrics.track.event("Denied account due to enterprise restricting signups", {email: val});
                                        self.deniedEmail(val);
                                    }

                                    self.isSso(result.isSso);
                                    self.ssoMessage(result.ssoMessage);

                                    callback({
                                        isValid: result.isValid,
                                        message: result.message,
                                    });
                                },
                            },
                        );
                    } else if (self.email() !== undefined) {
                        module.resetEmailFeedback(false);
                    }
                },
            },
        });
    if (defaults.email) {
        // triggers validation check on pre-filled emails
        self.email(defaults.email);
    }
    self.isEmailValidating = ko.observable(false);
    self.validatingEmailMsg = ko.observable(gettext("Checking email..."));
    self.emailDelayed.isValidating.subscribe(function (isValidating) {
        self.isEmailValidating(isValidating && self.email.isValid());
        module.resetEmailFeedback(isValidating);
    });

    // ---------------------------------------------------------------------
    self.password = ko.observable(defaults.password)
        .extend({
            required: {
                message: gettext("Please specify a password."),
                params: true,
            },
        });
    self.passwordDelayed = ko.pureComputed(self.password)
        .extend(_rateLimit)
        .extend({
            minimumPasswordLength: {params: initialPageData.get('minimumPasswordLength'),
                message: _.template(gettext("Password must have at least <%- passwordLength %>" +
                " characters."))({passwordLength: initialPageData.get('minimumPasswordLength')})},
            zxcvbnPassword: initialPageData.get('minimumZxcvbnScore'),
        });


    // --- Optional for test ----
    self.phoneNumber = ko.observable();

    // ---------------------------------------------------------------------
    // Step 2
    // ---------------------------------------------------------------------
    self.projectName = ko.observable(defaults.project_name)
        .extend({
            required: {
                message: gettext("Please specify a project name."),
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
                message: gettext("Please specify."),
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
    self.isPersonaChoiceProfessional = ko.computed(function () {
        return self.isPersonaChoiceChosen()
            && !(self.isPersonaChoiceOther() || self.personaChoice() === 'Personal');
    });
    self.isPersonaValid = ko.computed(function () {
        if (!self.hasPersonaFields) {
            return true;
        }
        return self.isPersonaChoiceChosen()
               && (!self.isPersonaChoiceOther() || self.isPersonaChoiceOtherPresent());
    });

    // For 'Organization or Company' Field
    self.hasCompanyNameField = $(containerSelector).find("[name='company_name']").length;
    self.companyName = ko.observable(defaults.company_name)
        .extend({
            required: {
                message: gettext("Please list your organization or company name."),
                params: true,
            },
        });
    self.requireCompanyName = ko.computed(function () {
        return self.hasCompanyNameField && self.isPersonaChoiceProfessional();
    });
    self.isCompanyNameValid = ko.computed(function () {
        return !self.requireCompanyName() || self.companyName.isValid();
    });

    // ---------------------------------------------------------------------
    // Form Functionality
    // ---------------------------------------------------------------------
    self.steps = ko.observableArray(steps);
    self.currentStep = ko.observable(0);

    self.currentStep.subscribe(function (newValue) {
        if (newValue === 1) {
            noopMetrics.track.event("Clicked Next button on Step 1 of CommCare signup");
        }
    });

    var _getDataForSubmission = function () {
        var password = self.password();
        var data = {
            full_name: self.fullName(),
            email: self.email(),
            password: password,
            project_name: self.projectName(),
            eula_confirmed: self.eulaConfirmed(),
            phone_number: module.getPhoneNumberFn() || self.phoneNumber(),
            atypical_user: defaults.atypical_user,
        };
        if (self.hasPersonaFields) {
            _.extend(data, {
                persona: self.personaChoice(),
                persona_other: self.isPersonaChoiceOther() ? self.personaOther() : '',
            });
        }
        if (self.requireCompanyName()) {
            _.extend(data, {
                company_name: self.companyName(),
            });
        }
        return data;
    };

    var _getFormStepUi = function (stepNum) {
        return $(containerSelector + " form ." + self.steps()[stepNum]);
    };

    self.isStepOneValid = ko.computed(function () {
        var isPasswordValid;
        if (self.isSso()) {
            isPasswordValid = true;
        } else {
            isPasswordValid = (
                self.password() !== undefined
                && self.password.isValid()
                && self.passwordDelayed.isValid()
            );
        }

        return self.fullName() !== undefined
            && self.email() !== undefined
            && self.fullName.isValid()
            && self.email.isValid()
            && self.emailDelayed.isValid()
            && !self.emailDelayed.isValidating()
            && isPasswordValid;
    });

    self.disableNextStepOne = ko.computed(function () {
        return !self.isStepOneValid();
    });

    self.isStepTwoValid = ko.computed(function () {
        return self.projectName() !== undefined
            && self.projectName.isValid()
            && self.isCompanyNameValid()
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

    // for SSO
    self.isSsoSuccess = ko.observable(false);
    self.ssoLoginUrl = ko.observable('');
    self.ssoIdpName = ko.observable('');

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
        module.submitAttemptAnalytics(submitData);

        module.rmi(
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
                        if (self.isSso()) {
                            self.isSsoSuccess(true);
                            self.ssoLoginUrl(response.ssoLoginUrl);
                            self.ssoIdpName(response.ssoIdpName);
                        } else {
                            self.isSubmitSuccess(true);
                        }
                        module.submitSuccessAnalytics(_.extend({}, submitData, {
                            email: self.email(),
                            deniedEmail: self.deniedEmail(),
                        }));
                        if (self.isSso()) {
                            setTimeout(function () {
                                window.location = self.ssoLoginUrl();
                            }, 3000);
                        }
                    }
                },
                error: function () {
                    self.isSubmitting(false);
                    self.hasServerError(true);
                },
            },
        );
        self.nextStep();
    };

    return self;
};

export default {
    setResetEmailFeedbackFn: function (callback) {
        // use this function to reset the form-control-feedback ui
        // in the email form so that it removes the waiting / checking email note
        // or adds it if the validator is still in async validation mode
        module.resetEmailFeedback = callback;
    },
    setSubmitAttemptFn: function (callback) {
        module.submitAttemptFn = callback;
    },
    setPhoneNumberInput: function (inputSelector) {
        var $number = $(inputSelector),
            numberWidget = intlTelInput($number[0], {
                containerClass: "w-100",
                separateDialCode: true,
                loadUtils: () => import("intl-tel-input/utils"),
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
        $number.keydown(function (e) {
            // prevents non-numeric numbers from being entered.
            // from http://stackoverflow.com/questions/995183/how-to-allow-only-numeric-0-9-in-html-inputbox-using-jquery
            // Allow: backspace, delete, tab, escape, enter and .
            if ($.inArray(e.keyCode, [46, 8, 9, 27, 13, 110, 190]) !== -1 ||
                // Allow: Ctrl+A, Command+A
                (e.keyCode === 65 && (e.ctrlKey === true || e.metaKey === true)) ||
                // Allow: home, end, left, right, down, up
                (e.keyCode >= 35 && e.keyCode <= 40)
            ) {
                // let it happen, don't do anything
                return;
            }

            // Ensure that it is a number and stop the keypress
            if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
                e.preventDefault();
            }
        });
        module.getPhoneNumberFn = function () {
            return numberWidget.getNumber();
        };
    },
    initRMI: function (rmiUrl) {
        module.rmiUrl = rmiUrl;
        module.csrf = $("#csrfTokenContainer").val();

        module.rmi = function (remoteMethod, data, options) {
            options = options || {};
            options.headers = {"DjNg-Remote-Method": remoteMethod};
            var _rmi = RMI(module.rmiUrl, module.csrf);
            return _rmi("", data, options);
        };
    },
    showPasswordFeedback: function () {
        module.showPasswordFeedback = true;
    },
    setOnModuleLoad: function (callback) {
        module.onModuleLoad = callback;
    },
    formViewModel: formViewModel,
};
