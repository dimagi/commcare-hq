'use strict';

hqDefine("users/js/react_mobile_workers",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'analytix/js/google',
    'jquery.rmi/jquery.rmi',
    'zxcvbn/dist/zxcvbn',
    'locations/js/widgets',
    'users/js/custom_data_fields',
    'hqwebapp/js/bootstrap3/components.ko', // for pagination
    'hqwebapp/js/bootstrap3/validators.ko', // email address validation
    'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min',
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties,
    googleAnalytics,
    RMI,
    zxcvbn,
    locationsWidgets,
    customDataFields
) {
    var STATUS = {
        NONE: '',
        PENDING: 'pending',
        SUCCESS: 'success',
        WARNING: 'warning',
        ERROR: 'danger',
        DISABLED: 'disabled',
    };

    var userModel = function (options) {
        options = options || {};
        options = _.defaults(options, {
            creation_status: STATUS.NONE,
            creation_error: "",
            username: '',
            first_name: '',
            last_name: '',
            location_id: '',
            password: '',
            user_id: '',
            force_account_confirmation: false,
            email: '',
            send_account_confirmation_email: false,
            force_account_confirmation_by_sms: false,
            phone_number: '',
            is_active: true,
            is_account_confirmed: true,
            deactivate_after_date: '',
        });

        var self = ko.mapping.fromJS(options);
        self.custom_fields = customDataFields.customDataFieldsEditor({
            profiles: initialPageData.get('custom_fields_profiles'),
            profile_slug: initialPageData.get('custom_fields_profile_slug'),
            slugs: initialPageData.get('custom_fields_slugs'),
        });

        self.email.extend({
            emailRFC2822: true,
        });

        // used by two-stage provisioning
        self.emailRequired = ko.observable(self.force_account_confirmation());
        self.sendConfirmationEmailEnabled = ko.observable(self.force_account_confirmation());

        // used by two-stage sms provisioning
        self.phoneRequired = ko.observable(self.force_account_confirmation_by_sms());

        self.passwordEnabled = ko.observable(!(self.force_account_confirmation_by_sms() || self.force_account_confirmation()));

        self.action_error = ko.observable('');  // error when activating/deactivating a user

        self.edit_url = ko.computed(function () {
            return initialPageData.reverse('edit_commcare_user', self.user_id());
        });

        self.is_active.subscribe(function (newValue) {
            var urlName = newValue ? 'activate_commcare_user' : 'deactivate_commcare_user',
                $modal = $('#' + (newValue ? 'activate_' : 'deactivate_') + self.user_id());

            $modal.find(".btn").addSpinnerToButton();
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse(urlName, self.user_id()),
                success: function (data) {
                    $modal.modal('hide');
                    if (data.success) {
                        self.action_error('');
                    } else {
                        self.action_error(data.error);
                    }
                },
                error: function () {
                    $modal.modal('hide');
                    self.action_error(gettext("Issue communicating with server. Try again."));
                },
            });
        });

        self.sendConfirmationEmail = function () {
            var urlName = 'send_confirmation_email';
            var $modal = $('#confirm_' + self.user_id());
            $modal.find(".btn").disableButton();
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse(urlName, self.user_id()),
                success: function (data) {
                    $modal.find(".btn").enableButton();
                    $modal.modal('hide');
                    if (data.success) {
                        self.action_error('');
                    } else {
                        self.action_error(data.error);
                    }

                },
                error: function () {
                    $modal.find(".btn").enableButton();
                    $modal.modal('hide');
                    self.action_error(gettext("Issue communicating with server. Try again."));
                },
            });
        };

        self.sendConfirmationSMS = function () {
            var urlName = 'send_confirmation_sms';
            var $modal = $('#confirm_' + self.user_id());

            $modal.find(".btn").addSpinnerToButton();
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse(urlName, self.user_id()),
                success: function (data) {
                    $modal.modal('hide');
                    if (data.success) {
                        self.action_error('');
                    } else {
                        self.action_error(data.error);
                    }

                },
                error: function () {
                    $modal.modal('hide');
                    $modal.find(".btn").removeSpinnerFromButton();
                    self.action_error(gettext("Issue communicating with server. Try again."));
                },
            });
        };

        return self;
    };

    var newUserCreationModel = function (options) {
        assertProperties.assertRequired(options, [
            'custom_fields_slugs',
            'skip_standard_password_validations',
            'location_url',
            'require_location_id',
            'strong_mobile_passwords',
            'show_deactivate_after_date',
        ]);

        var self = {};
        self.STATUS = STATUS;   // make status constants available to bindings in HTML

        self.customFieldSlugs = options.custom_fields_slugs; // Required custom fields this domain has configured
        self.stagedUser = ko.observable();                   // User in new user modal, not yet sent to server
        self.newUsers = ko.observableArray();                // New users sent to server

        // Username handling
        self.usernameAvailabilityStatus = ko.observable();
        self.usernameStatusMessage = ko.observable();

        // Password handling
        self.isSuggestedPassword = ko.observable(false);

        // These don't need to be observables, but it doesn't add much overhead
        // and eliminates the need to remember which flags are observable and which aren't
        self.useStrongPasswords = ko.observable(options.strong_mobile_passwords);
        self.skipStandardValidations = ko.observable(options.skip_standard_password_validations);

        self.passwordStatus = ko.computed(function () {
            if (!self.stagedUser()) {
                return self.STATUS.NONE;
            }

            if (self.stagedUser().force_account_confirmation()) {
                return self.STATUS.DISABLED;
            }

            if (self.stagedUser().force_account_confirmation_by_sms()) {
                return self.STATUS.DISABLED;
            }

            if (!self.useStrongPasswords()) {
                // No validation
                return self.STATUS.NONE;
            }

            var password = self.stagedUser().password();
            if (!password) {
                return self.STATUS.NONE;
            }
            if (self.isSuggestedPassword()) {
                return self.STATUS.WARNING;
            }

            if (!self.skipStandardValidations()) {
                // Standard validation
                var score = zxcvbn(password, ['dimagi', 'commcare', 'hq', 'commcarehq']).score;
                var minimumZxcvbnScore = initialPageData.get('minimumZxcvbnScore');
                if (self.passwordSatisfyLength()) {
                    if (score >= minimumZxcvbnScore) {
                        return self.STATUS.SUCCESS;
                    } else if (self < minimumZxcvbnScore - 1) {
                        return self.STATUS.ERROR;
                    }
                    return self.STATUS.WARNING;

                } else {
                    return self.STATUS.ERROR;
                }
            }
            return self.STATUS.SUCCESS;
        });

        self.passwordSatisfyLength = ko.computed(function () {
            if (self.stagedUser()) {
                var minimumPasswordLength = initialPageData.get('minimumPasswordLength');
                var password = self.stagedUser().password();
                if (!password) {
                    return true;
                }
                if (password.length < minimumPasswordLength) {
                    return false;
                }
            }
            return true;
        });

        self.requiredEmailMissing = ko.computed(function () {
            return self.stagedUser() && self.stagedUser().emailRequired() && !self.stagedUser().email();
        });

        self.emailIsInvalid = ko.computed(function () {
            return self.stagedUser() && !self.stagedUser().email.isValid();
        });

        self.emailStatus = ko.computed(function () {

            if (!self.stagedUser()) {
                return self.STATUS.NONE;
            }

            if (self.requiredEmailMissing() || self.emailIsInvalid()) {
                return self.STATUS.ERROR;
            }
        });

        self.emailStatusMessage = ko.computed(function () {

            if (self.requiredEmailMissing()) {
                return gettext('Email address is required when users confirm their own accounts.');
            } else if (self.emailIsInvalid()) {
                return gettext('Please enter a valid email address.');
            }
            return "";
        });

        self.requiredPhoneMissing = ko.computed(function () {
            return self.stagedUser() && self.stagedUser().phoneRequired() && !self.stagedUser().phone_number();
        });

        self.phoneIsInvalid = ko.computed(function () {
            return self.stagedUser() && self.stagedUser().phone_number() && !self.stagedUser().phone_number().match(/^[0-9]+$/);
        });

        self.phoneStatus = ko.computed(function () {

            if (!self.stagedUser()) {
                return self.STATUS.NONE;
            }

            if (self.phoneStatusMessage()) {
                return self.STATUS.ERROR;
            }
        });

        self.phoneStatusMessage = ko.computed(function () {

            if (self.requiredPhoneMissing()) {
                return gettext('Phone number is required when users confirm their own accounts by sms.');
            }

            if (self.phoneIsInvalid()) {
                return gettext('Phone number should contain only digits 0-9.');
            }

            return "";
        });

        self.generateStrongPassword = function () {
            function pick(possible, min, max) {
                let n,
                    chars = '';

                if (typeof max === 'undefined') {
                    n = min;
                } else {
                    n = min + Math.floor(Math.random() * (max - min + 1));
                }

                for (var i = 0; i < n; i++) {
                    chars += possible.charAt(Math.floor(Math.random() * possible.length));
                }

                return chars;
            }

            function shuffle(password) {
                var array = password.split('');
                var tmp,
                    current,
                    top = array.length;

                if (top) {
                    while (--top) {
                        current = Math.floor(Math.random() * (top + 1));
                        tmp = array[current];
                        array[current] = array[top];
                        array[top] = tmp;
                    }
                }

                return array.join('');
            }

            var specials = '!@#$%^&*()_+{}:"<>?\|[];\',./`~';   // eslint-disable-line no-useless-escape
            var lowercase = 'abcdefghijklmnopqrstuvwxyz';
            var uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
            var numbers = '0123456789';

            var all = specials + lowercase + uppercase + numbers;

            var password = '';
            password += pick(specials, 1);
            password += pick(lowercase, 1);
            password += pick(uppercase, 1);
            password += pick(numbers, 1);
            password += pick(all, 6, 10);
            return shuffle(password);
        };

        self.stagedUser.subscribe(function (user) {
            user.username.subscribe(_.debounce(function (newValue) {
                if (!newValue) {
                    self.usernameAvailabilityStatus(null);
                    self.usernameStatusMessage('');
                    return;
                }

                self.usernameAvailabilityStatus(self.STATUS.PENDING);
                self.usernameStatusMessage(gettext("Checking availability..."));
            }, 100));
            user.password.subscribe(function () {
                self.isSuggestedPassword(false);
            });
            user.force_account_confirmation.subscribe(function (enabled) {
                if (enabled) {
                    // make email required
                    user.emailRequired(true);
                    // clear and disable password input
                    user.password('');
                    user.passwordEnabled(false);
                    user.sendConfirmationEmailEnabled(true);
                } else {
                    // make email optional
                    user.emailRequired(false);
                    // enable password input
                    user.passwordEnabled(true);
                    user.sendConfirmationEmailEnabled(false);
                    // uncheck email confirmation box if it was checked
                    user.send_account_confirmation_email(false);
                }
            });
            user.force_account_confirmation_by_sms.subscribe(function (enabled) {
                if (enabled) {
                    // make phone number required
                    user.phoneRequired(true);
                    // clear and disable password input
                    user.password('');
                    user.passwordEnabled(false);
                    user.sendConfirmationEmailEnabled(true);
                } else {
                    // make phone number optional
                    user.phoneRequired(false);
                    // enable password input
                    user.passwordEnabled(true);
                }
            });
        });

        self.initializeUser = function () {
            self.stagedUser(userModel({
                password: self.useStrongPasswords() ? self.generateStrongPassword() : '',
            }));
            if (self.useStrongPasswords()) {
                self.isSuggestedPassword(true);
            }
            self.usernameAvailabilityStatus(null);
            self.usernameStatusMessage(null);

            var $locationSelect = $("#id_location_id");
            if ($locationSelect.length) {
                locationsWidgets.initAutocomplete($locationSelect);
            }

            if (options.show_deactivate_after_date) {
                $('#id_deactivate_after_date').datetimepicker({
                    format: 'MM-y',
                });
            }

            googleAnalytics.track.event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        self.getDeactivateAfterDate = function () {
            if (options.show_deactivate_after_date) {
                return $('#id_deactivate_after_date').val();
            }
        };

        self.allowSubmit = ko.computed(function () {
            if (!self.stagedUser()) {
                return false;
            }
            if (!self.stagedUser().username()) {
                return false;
            }
            if (self.stagedUser().passwordEnabled()) {
                if  (!self.stagedUser().password()) {
                    return false;
                }
                if (self.useStrongPasswords()) {
                    if (!self.isSuggestedPassword() && self.passwordStatus() !== self.STATUS.SUCCESS) {
                        return false;
                    }
                }
            }
            if (self.requiredEmailMissing() || self.emailIsInvalid()) {
                return false;
            }
            if (self.requiredPhoneMissing() || self.phoneIsInvalid()) {
                return false;
            }
            if (options.require_location_id && !self.stagedUser().location_id()) {
                return false;
            }
            if (self.usernameAvailabilityStatus() !== self.STATUS.SUCCESS) {
                return false;
            }
            if (_.find(self.customFieldSlugs, function (slug) {
                return !self.stagedUser().custom_fields[slug].value();
            })) {
                return false;
            }
            return true;
        });

        self.submitNewUser = function () {
        };

        return self;
    };
    $(function () {
        var newUserCreation = newUserCreationModel({
            custom_fields_slugs: initialPageData.get('custom_fields_slugs'),
            skip_standard_password_validations: initialPageData.get('skip_standard_password_validations'),
            location_url: initialPageData.reverse('location_search'),
            require_location_id: !initialPageData.get('can_access_all_locations'),
            strong_mobile_passwords: initialPageData.get('strong_mobile_passwords'),
            show_deactivate_after_date: initialPageData.get('show_deactivate_after_date'),
        });
        $("#new-user-modal-trigger").koApplyBindings(newUserCreation);
    });
});
