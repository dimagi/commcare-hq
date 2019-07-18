/* global RMI, zxcvbn */
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
 *    password has to meet a minimum strength requirement, based on the zxcvbn strength algorithm.
 *  - If strong mobile passwords are on AND the server setting ENABLE_DRACONIAN_SECURITY_FEATURES is on, the
 *    password instead has to meet a specific set of requirements (8+ chars, at least one special character, etc.).
 *  - If any validation is being used, we automatically generate a suggested password that passes validation.
 *  - Independently of password validation, if the server setting OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE is on,
 *    passwords are encrypted before the new user is sent to the server for creation.
 */
hqDefine("users/js/mobile_workers", function () {
    // These are used as css classes, so the values of success/warning/error need to be what they are.
    var STATUS = {
        NONE: '',
        PENDING: 'pending',
        SUCCESS: 'success',
        WARNING: 'warning',
        ERROR: 'danger',
    };

    var rmi = function () {};

    var userModel = function (options) {
        options = options || {};
        options = _.defaults(options, {
            creation_status: STATUS.NONE,
            username: '',
            first_name: '',
            last_name: '',
            location_id: '',
            password: '',
            user_id: '',
            is_active: true,
            custom_fields: {},
        });

        // Manually turn custom_fields into an object of observables, since the default ko.mapping doesn't handle this
        options.custom_fields = _.mapObject(options.custom_fields, function (value) {
            return ko.observable(value);
        });
        var self = ko.mapping.fromJS(options);

        self.action_error = ko.observable('');  // error when activating/deactivating a user

        self.edit_url = ko.computed(function () {
            return hqImport("hqwebapp/js/initial_page_data").reverse('edit_commcare_user', self.user_id());
        });

        self.is_active.subscribe(function (newValue) {
            var urlName = newValue ? 'activate_commcare_user' : 'deactivate_commcare_user',
                $modal = $('#' + (newValue ? 'activate_' : 'deactivate_') + self.user_id());

            $modal.find(".btn").addSpinnerToButton();
            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse(urlName, self.user_id()),
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
                url: hqImport("hqwebapp/js/initial_page_data").reverse('paginate_mobile_workers'),
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
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, [
            'custom_field_slugs',
            'draconian_security',
            'implement_password_obfuscation',
            'location_url',
            'require_location_id',
            'strong_mobile_passwords',
        ]);

        var self = {};
        self.STATUS = STATUS;   // make status constants available to bindings in HTML

        self.customFieldSlugs = options.custom_field_slugs; // Required custom fields this domain has configured
        self.stagedUser = ko.observable();                  // User in new user modal, not yet sent to server
        self.newUsers = ko.observableArray();               // New users sent to server

        // Username handling
        self.usernameAvailabilityStatus = ko.observable();
        self.usernameStatusMessage = ko.observable();

        // Password handling
        self.isSuggestedPassword = ko.observable(false);

        // These don't need to be observables, but it doesn't add much overhead
        // and eliminates the need to remember which flags are observable and which aren't
        self.useStrongPasswords = ko.observable(options.strong_mobile_passwords);
        self.useDraconianSecurity = ko.observable(options.draconian_security);
        self.implementPasswordObfuscation = ko.observable(options.implement_password_obfuscation);

        self.passwordStatus = ko.computed(function () {
            if (!self.useStrongPasswords()) {
                // No validation
                return self.STATUS.NONE;
            }

            if (!self.stagedUser()) {
                return self.STATUS.NONE;
            }

            var password = self.stagedUser().password();
            if (!password) {
                return self.STATUS.NONE;
            }
            if (self.isSuggestedPassword()) {
                return self.STATUS.WARNING;
            }

            if (self.useDraconianSecurity()) {
                if (!(
                    password.length >= 8 &&
                    /\W/.test(password) &&
                    /\d/.test(password) &&
                    /[A-Z]/.test(password)
                )) {
                    return self.STATUS.ERROR;
                }
                return self.STATUS.SUCCESS;
            }

            // Standard validation
            var score = zxcvbn(password, ['dimagi', 'commcare', 'hq', 'commcarehq']).score;
            if (score > 1) {
                return self.STATUS.SUCCESS;
            } else if (score < 1) {
                return self.STATUS.ERROR;
            }
            return self.STATUS.WARNING;
        });

        self.generateStrongPassword = function () {
            function pick(possible, min, max) {
                var n, chars = '';

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
                var tmp, current, top = array.length;

                if (top) while (--top) {
                    current = Math.floor(Math.random() * (top + 1));
                    tmp = array[current];
                    array[current] = array[top];
                    array[top] = tmp;
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
        });

        self.initializeUser = function () {
            self.stagedUser(userModel({
                password: self.useStrongPasswords() ? self.generateStrongPassword() : '',
                custom_fields: _.object(_.map(self.customFieldSlugs, function (slug) {
                    return [slug, ''];
                })),
            }));
            if (self.useStrongPasswords()) {
                self.isSuggestedPassword(true);
            }
            self.usernameAvailabilityStatus(null);
            self.usernameStatusMessage(null);

            $("#id_location_id").select2({
                minimumInputLength: 0,
                width: '100%',
                placeholder: gettext("Select location"),
                allowClear: 1,
                ajax: {
                    delay: 100,
                    url: options.location_url,
                    data: function (params) {
                        return {
                            name: params.term,
                        };
                    },
                    dataType: 'json',
                    processResults: function (data) {
                        return {
                            results: _.map(data.results, function (r) {
                                return {
                                    text: r.name,
                                    id: r.id,
                                };
                            }),
                        };
                    },
                },
            });

            hqImport('analytix/js/google').track.event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        self.allowSubmit = ko.computed(function () {
            if (!self.stagedUser()) {
                return false;
            }
            if (!self.stagedUser().username()) {
                return false;
            }
            if (!self.stagedUser().password()) {
                return false;
            }
            if (options.require_location_id && !self.stagedUser().location_id()) {
                return false;
            }
            if (self.usernameAvailabilityStatus() !== self.STATUS.SUCCESS) {
                return false;
            }
            if (self.useStrongPasswords()) {
                if (!self.isSuggestedPassword() && self.passwordStatus() !== self.STATUS.SUCCESS) {
                    return false;
                }
            }
            var fieldData = self.stagedUser().custom_fields;
            if (_.isObject(fieldData) && !_.isArray(fieldData)) {
                if (!_.every(fieldData, function (value) { return value(); })) {
                    return false;
                }
            }
            return true;
        });

        self.submitNewUser = function () {
            $("#new-user-modal").modal('hide');
            var newUser = userModel(ko.mapping.toJS(self.stagedUser));
            self.newUsers.push(newUser);
            newUser.creation_status(STATUS.PENDING);
            if (self.implementPasswordObfuscation()) {
                newUser.password(hqImport("nic_compliance/js/encoder")().encode(newUser.password()));
            }
            rmi('create_mobile_worker', {
                user: ko.mapping.toJS(newUser),
            }).done(function (data) {
                if (data.success) {
                    newUser.user_id(data.user_id);
                    newUser.creation_status(STATUS.SUCCESS);
                } else {
                    newUser.creation_status(STATUS.ERROR);
                }
            }).fail(function () {
                newUser.creation_status(STATUS.ERROR);
            });
        };

        return self;
    };

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            rmiInvoker = RMI(initialPageData.reverse('mobile_workers'), $("#csrfTokenContainer").val());
        rmi = function (remoteMethod, data) {
            return rmiInvoker("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };

        $("#users-list").koApplyBindings(usersListModel());

        var newUserCreation = newUserCreationModel({
            custom_field_slugs: initialPageData.get('custom_field_slugs'),
            draconian_security: initialPageData.get('draconian_security'),
            implement_password_obfuscation: initialPageData.get('implement_password_obfuscation'),
            location_url: initialPageData.reverse('child_locations_for_select2'),
            require_location_id: !initialPageData.get('can_access_all_locations'),
            strong_mobile_passwords: initialPageData.get('strong_mobile_passwords'),
        });
        $("#new-user-modal-trigger").koApplyBindings(newUserCreation);
        $("#new-user-modal").koApplyBindings(newUserCreation);
        $("#new-users-list").koApplyBindings(newUserCreation);
    });
});
