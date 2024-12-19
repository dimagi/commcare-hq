hqDefine('registration/js/user_login_form', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/utils/email',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko',
], function (
    $,
    _,
    ko,
    initialPageData,
    assertProperties,
    emailUtils
) {
    'use strict';

    var loginController = function (options) {
        assertProperties.assertRequired(options, [
            'initialUsername',
            'passwordField',
            'passwordFormGroup',
            'nextUrl',
            'isSessionExpiration',
        ]);
        var self = {};

        self.checkSsoLoginStatusUrl = initialPageData.reverse('check_sso_login_status');
        self.sessionExpirationSsoIframeUrl = initialPageData.reverse('iframe_sso_login_pending');
        self.nextUrl = options.nextUrl;
        self.isSessionExpiration = options.isSessionExpiration;
        self.passwordField = options.passwordField;
        self.passwordFormGroup = options.passwordFormGroup;

        self.authUsername = ko.observable(options.initialUsername);
        self.authUsername.subscribe(function (newValue) {
            if (emailUtils.validateEmail(newValue)) {
                if (self.continueTextPromise) {
                    self.continueTextPromise.abort();
                }
                self.updateContinueText();
            }
        });

        self.continueTextPromise = null;
        self.defaultContinueText = gettext("Continue");
        self.continueButtonText = ko.observable(self.defaultContinueText);
        self.showContinueButton = ko.observable(false);
        self.showContinueSpinner = ko.observable(false);

        self.isContinueDisabled = ko.computed(function () {
            return !emailUtils.validateEmail(self.authUsername());
        });

        self.showSignInButton = ko.observable(true);

        /**
         * This updates the "Continue" Button text with either "Continue"
         * or "Continue to <IdentityProvider>".
         * @param {boolean} expandPasswordField - (optional) if this is true, auto expand password field
         */
        self.updateContinueText = function (expandPasswordField) {
            if (_.isUndefined(expandPasswordField)) {
                expandPasswordField = false;
            }
            self.continueTextPromise = $.post(self.checkSsoLoginStatusUrl, {
                username: self.authUsername(),
            }, function (data) {
                if (data.continue_text) {
                    self.continueButtonText(data.continue_text);
                    if (self.showSignInButton()) {
                        self.resetLoginState();
                    }
                } else {
                    self.continueButtonText(self.defaultContinueText);
                    if (expandPasswordField) self.continueToPasswordLogin();
                }
            })
                .fail(function () {
                    self.continueButtonText(self.defaultContinueText);
                    if (expandPasswordField) self.continueToPasswordLogin();
                });
        };

        /**
         * This resets the login state to just the username field and the
         * "Continue <etc>" button.
         */
        self.resetLoginState = function () {
            self.passwordFormGroup.slideUp('fast', function() {
                self.showContinueButton(true);
                self.showSignInButton(false);
            });
        };

        /**
         * This decides whether we should ask the user for a password or
         * redirect the user to the SSO login page.
         */
        self.proceedToNextStep = function () {
            self.showContinueSpinner(true);
            $.post(self.checkSsoLoginStatusUrl, {
                username: self.authUsername(),
            }, function (data) {
                if (data.is_sso_required) {
                    self.continueToSsoLogin(data.sso_url);
                } else {
                    self.continueToPasswordLogin();
                }
            })
                .fail(function () {
                    self.continueToPasswordLogin();
                })
                .always(function () {
                    self.showContinueSpinner(false);
                });
        };

        /**
         * This overrides the natural "next step" for the enter key,
         * which is to focus on the password field. Instead we want to "click"
         * the continue button then re-focus on the password field if needed.
         */
        self.continueOnEnter = function () {
            if (self.isContinueDisabled()) return;
            self.proceedToNextStep();
        };

        self.continueToSsoLogin = function (ssoUrl) {
            if (self.nextUrl) {
                // note ssoUrl already contains ?username=foo
                ssoUrl = ssoUrl + "&next=" + self.nextUrl;
            }
            if (self.isSessionExpiration) {
                // the reason why we do this for the session expiration popup
                // is that Entra ID does not load in cross origin iframes.
                window.open(ssoUrl);
                window.location = self.sessionExpirationSsoIframeUrl;
            } else {
                window.location = ssoUrl;
            }
        };

        self.continueToPasswordLogin = function () {
            self.passwordFormGroup.slideDown('fast', function() {
                self.showContinueButton(false);
                self.showSignInButton(true);
                self.passwordField.focus();
            });
        };

        self.init = function () {
            if (self.authUsername()) {
                // make sure that on initialization we update the continue text
                // if the username field is already populated.
                self.updateContinueText(true);
            }
        };

        return self;
    };

    return {
        loginController: loginController,
    }
});
