/**
 *  This file controls the mobile workers list page, which lists existing mobile workers
 *  and allows creation of new ones. It contains the following models and applies their
 *  bindings on document ready.
 *
 *  userModel: A single user, could be pre-existing or just created.
 *  usersListModel: A panel of all pre-existing users. Has some interactivity: search, activate/deactivate.
 *  newUserCreationModel: A modal to create a new user, plus a panel that lists those just-created users and their
 *      server status (pending, success, error).
 *
 *  When creating a new user, validation for their password depends on a few settings.
 *  - By default, passwords are not validated.
 *  - If the project requires strong mobile passwords (Project Settings > Privacy and Security), the
 *    password has to meet a minimum strength requirement, based on the zxcvbn strength algorithm,
 *    as well as a minimum length requirment (the length is configurable).
 *  - If any validation is being used, we automatically generate a suggested password that passes validation.
 */
hqDefine("users/js/mobile_workers",[
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
    'use strict';
    // These are used as css classes, so the values of success/warning/error need to be what they are.
    var STATUS = {
        NONE: '',
        PENDING: 'pending',
        SUCCESS: 'success',
        WARNING: 'warning',
        ERROR: 'danger',
        DISABLED: 'disabled',
    };

    var rmi = function () {};
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

    var usersListModel = function () {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');
        self.deactivatedOnly = ko.observable(false);

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable();

        // Visibility of spinners, messages, and user table
        self.hasError = ko.observable(false);
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.projectHasUsers = ko.observable(true);

        self.showProjectHasNoUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.projectHasUsers();
        });

        self.showNoUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.totalItems() && !self.showProjectHasNoUsers();
        });

        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.showNoUsers() && !self.showProjectHasNoUsers();
        });

        self.deactivatedOnly.subscribe(function () {
            self.goToPage(1);
        });

        self.goToPage = function (page) {
            self.users.removeAll();
            self.hasError(false);
            self.showPaginationSpinner(true);
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('paginate_mobile_workers'),
                data: {
                    page: page || 1,
                    query: self.query(),
                    limit: self.itemsPerPage(),
                    showDeactivatedUsers: self.deactivatedOnly(),
                },
                success: function (data) {
                    self.totalItems(data.total);
                    self.users(_.map(data.users, function (user) {
                        return userModel(user);
                    }));

                    if (!self.query()) {
                        self.projectHasUsers(!!data.users.length);
                    }
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(false);
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(true);
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
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
                rmi('check_username', {
                    username: newValue,
                }).done(function (data) {
                    // There are likely to be a few of these requests in a row.
                    // If this isn't the most recent one, bail.
                    if (newValue !== user.username()) {
                        return;
                    }
                    if (data.success) {
                        self.usernameAvailabilityStatus(self.STATUS.SUCCESS);
                        self.usernameStatusMessage(data.success);
                    } else if (data.warning) {
                        self.usernameAvailabilityStatus(self.STATUS.WARNING);
                        self.usernameStatusMessage(data.warning);
                    } else {
                        self.usernameAvailabilityStatus(self.STATUS.ERROR);
                        self.usernameStatusMessage(data.error);
                    }
                }).fail(function () {
                    self.usernameAvailabilityStatus(self.STATUS.ERROR);
                    self.usernameStatusMessage(gettext('Issue connecting to server. Check Internet connection.'));
                });
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
            $("#new-user-modal").modal('hide');
            var newUser = userModel(ko.mapping.toJS(self.stagedUser));
            self.newUsers.push(newUser);
            newUser.creation_status(STATUS.PENDING);
            // if we disabled the password, set it just in time before going to the server
            if (!newUser.passwordEnabled()) {
                newUser.password(self.generateStrongPassword());
            }
            rmi('create_mobile_worker', {
                user: _.extend(ko.mapping.toJS(newUser), {
                    custom_fields: self.stagedUser().custom_fields.serialize(),
                    deactivate_after_date: self.getDeactivateAfterDate(),
                }),
            }).done(function (data) {
                if (data.success) {
                    newUser.user_id(data.user_id);
                    newUser.creation_status(STATUS.SUCCESS);
                } else {
                    newUser.creation_status(STATUS.ERROR);
                    if (data.error) {
                        newUser.creation_error(data.error);
                    }
                }
            }).fail(function () {
                newUser.creation_status(STATUS.ERROR);
            });
        };

        return self;
    };

    $(function () {
        var rmiInvoker = RMI(initialPageData.reverse('mobile_workers'), $("#csrfTokenContainer").val());
        rmi = function (remoteMethod, data) {
            return rmiInvoker("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };
        $("#users-list").koApplyBindings(usersListModel());

        var newUserCreation = newUserCreationModel({
            custom_fields_slugs: initialPageData.get('custom_fields_slugs'),
            skip_standard_password_validations: initialPageData.get('skip_standard_password_validations'),
            location_url: initialPageData.reverse('location_search'),
            require_location_id: !initialPageData.get('can_access_all_locations'),
            strong_mobile_passwords: initialPageData.get('strong_mobile_passwords'),
            show_deactivate_after_date: initialPageData.get('show_deactivate_after_date'),
        });
        $("#new-user-modal-trigger").koApplyBindings(newUserCreation);
        $("#new-user-modal").koApplyBindings(newUserCreation);
        $("#new-users-list").koApplyBindings(newUserCreation);
    });
});
