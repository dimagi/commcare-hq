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
 */
hqDefine("users/js/mobile_workers", function () {
    var NEW_USER_STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
    };

    var rmi = function () {};

    var userModel = function (options) {
        options = options || {};
        options = _.defaults(options, {
            creationStatus: NEW_USER_STATUS.NEW,
            username: '',
            first_name: '',
            last_name: '',
            location_id: '',
            password: '',
            user_id: '',
            is_active: true,
            customFields: {},
        });

        // Manually turn customFields into an object of observables, since the default ko.mapping doesn't handle this
        options.customFields = _.mapObject(options.customFields, function (value) {
            return ko.observable(value);
        });
        var self = ko.mapping.fromJS(options);

        self.action_error = ko.observable('');

        self.editUrl = ko.computed(function () {
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
        self.goToPage(1);
        return self;
    };

    var newUserCreationModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, [
            'custom_field_slugs',
            'location_url',
            'require_location_id',
            'strong_mobile_passwords',
        ]);

        var self = {};

        self.customFieldSlugs = options.custom_field_slugs;
        self.stagedUser = ko.observable();              // User in new user modal, not yet sent to server
        self.newUsers = ko.observableArray();           // New users sent to server

        // Username handling
        USERNAME_STATUS = {
            PENDING: 'pending',
            TAKEN: 'taken',
            AVAILABLE: 'available',
            AVAILABLE_WARNING: 'warning',
            ERROR: 'error',
        };
        self.usernameAvailabilityStatus = ko.observable();
        self.usernameStatusMessage = ko.observable();
        self.usernameIsPending = ko.computed(function () {
            return self.usernameAvailabilityStatus() === USERNAME_STATUS.PENDING;
        });
        self.usernameIsAvailable = ko.computed(function () {
            return self.usernameAvailabilityStatus() === USERNAME_STATUS.AVAILABLE;
        });
        self.usernameIsWarning = ko.computed(function () {
            return self.usernameAvailabilityStatus() === USERNAME_STATUS.AVAILABLE_WARNING;
        });
        self.usernameIsError = ko.computed(function () {
            return self.usernameAvailabilityStatus() === USERNAME_STATUS.ERROR;
        });

        // Password handling
        self.PASSWORD_STATUS = {
            STRONG: 'strong',
            ALMOST: 'almost',
            WEAK: 'weak',
            PENDING: 'pending',
        };
        self.validatePassword = ko.observable(options.strong_mobile_passwords);
        self.passwordStatus = ko.computed(function () {
            if (!self.validatePassword()) {
                return self.PASSWORD_STATUS.PENDING;
            }

            if (!self.stagedUser()) {
                return self.PASSWORD_STATUS.PENDING;
            }

            var password = self.stagedUser().password();
            if (!password) {
                return self.PASSWORD_STATUS.PENDING;
            }

            var score = zxcvbn(password, ['dimagi', 'commcare', 'hq', 'commcarehq']).score;
            if (score > 1) {
                return self.PASSWORD_STATUS.STRONG;
            } else if (score < 1) {
                return self.PASSWORD_STATUS.WEAK;
            }
            return self.PASSWORD_STATUS.ALMOST;
        });

        self.stagedUser.subscribe(function (user) {
            user.username.subscribe(_.debounce(function (newValue) {
                if (!newValue) {
                    self.usernameAvailabilityStatus(null);
                    return;
                }

                self.usernameAvailabilityStatus(USERNAME_STATUS.PENDING);
                rmi('check_username', {
                    username: newValue,
                }).done(function (data) {
                    if (data.success) {
                        self.usernameAvailabilityStatus(USERNAME_STATUS.AVAILABLE);
                        self.usernameStatusMessage(data.success);
                    } else if (data.warning) {
                        self.usernameAvailabilityStatus(USERNAME_STATUS.AVAILABLE_WARNING);
                        self.usernameStatusMessage(data.warning);
                    } else {
                        self.usernameAvailabilityStatus(USERNAME_STATUS.ERROR);
                        self.usernameStatusMessage(data.error);
                    }
                }).fail(function () {
                    self.usernameAvailabilityStatus(USERNAME_STATUS.ERROR);
                    self.usernameStatusMessage(gettext('Issue connecting to server. Check Internet connection.'));
                });
            }, 300));
        });

        self.initializeUser = function () {
            self.stagedUser(userModel({
                customFields: _.object(_.map(self.customFieldSlugs, function (slug) {
                    return [slug, ''];
                })),
            }));
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
            if (!self.usernameIsAvailable()) {
                return false;
            }
            var fieldData = self.stagedUser().customFields;
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
            newUser.creationStatus(NEW_USER_STATUS.PENDING);
            if (hqImport("hqwebapp/js/initial_page_data").get("implement_password_obfuscation")) {
                // TODO: draconian password requirements
                //newWorker.password = (hqImport("nic_compliance/js/encoder")()).encode(newWorker.password);
            }
            rmi('create_mobile_worker', {
                mobileWorker: ko.mapping.toJS(newUser),
            }).done(function (data) {
                if (data.success) {
                    newUser.user_id(data.user_id);
                    newUser.creationStatus(NEW_USER_STATUS.SUCCESS);
                } else {
                    newUser.creationStatus(NEW_USER_STATUS.WARNING);
                }
            }).fail(function () {
                newUser.creationStatus(NEW_USER_STATUS.WARNING);
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
            location_url: initialPageData.reverse('child_locations_for_select2'),
            require_location_id: !initialPageData.get('can_access_all_locations'),
            strong_mobile_passwords: initialPageData.get('strong_mobile_passwords'),
        });
        $("#new-user-modal-trigger").koApplyBindings(newUserCreation);
        $("#new-user-modal").koApplyBindings(newUserCreation);
        $("#new-users-list").koApplyBindings(newUserCreation);
    });
});
