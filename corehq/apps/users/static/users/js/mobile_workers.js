hqDefine("users/js/mobile_workers", function() {
    var mobileWorkerModel = function(options) {
        var self = {},
            defaults = {
                username: '',
                password: '',
                customFields: {},
                first_name: '',
                last_name: '',
                phoneNumbers: [],
                user_id: '',
                location: null,
                dateRegistered: '',
                editUrl: '#',
                action: 'deactivate',
                mark_activated: false,
                mark_deactivated: false,
                action_error: '',
            };
        options = _.defaults(options || {}, defaults);

        self.username = ko.observable(options.username);
        self.password = ko.observable(options.password);
        self.customFields = options.customFields;
        self.first_name = ko.observable(options.first_name);
        self.last_name = ko.observable(options.last_name);
        self.phoneNumbers = ko.observableArray(options.phoneNumbers);
        self.user_id = ko.observable(options.user_id);
        self.location = ko.observable(options.location);
        self.dateRegistered = ko.observable(options.dateRegistered);
        self.editUrl = ko.observable(options.editUrl);
        self.action = ko.observable(options.action);
        self.mark_activated = ko.observable(options.mark_activated);
        self.mark_deactivated = ko.observable(options.mark_deactivated);
        self.action_error = ko.observable(options.action_error);

        self.clear = function() {
            self.username(defaults.username);
            self.password(defaults.password);
            self.customFields = defaults.customFields;
            self.first_name(defaults.first_name);
            self.last_name(defaults.last_name);
            self.phoneNumbers.removeAll();
            self.user_id(defaults.user_id);
            self.location(defaults.location);
            self.dateRegistered(defaults.dateRegistered);
            self.editUrl(defaults.editUrl);
            self.action(defaults.action);
            self.mark_activated(defaults.mark_activated);
            self.mark_deactivated(defaults.mark_deactivated);
            self.action_error(defaults.action_error);

            self.password('');
        };

        self.showActivate = ko.computed(function() {
            return self.action() === 'activate';
        });

        self.showDeactivate = ko.computed(function() {
            return self.action() === 'deactivate';
        });

        self.modifyStatus = function(isActive, button) {
            var urlName = isActive ? 'activate_commcare_user' : 'deactivate_commcare_user',
                modalId = (isActive ? 'activate_' : 'deactivate_') + self.user_id();
            $(button).addSpinnerToButton();

            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse(urlName, self.user_id()),
                data: {
                    is_active: isActive,
                },
                success: function(data) {
                    $('#' + modalId).modal('hide');
                    if (data.success) {
                        self.mark_activated(isActive);
                        self.mark_deactivated(!isActive);
                        self.action_error('');
                    } else {
                        self.action_error(data.error);
                    }
                },
                error: function() {
                    $('#' + modalId).modal('hide');
                    self.action_error(gettext("Issue communicating with server. Try again."));
                },
            });
        };

        return self;
    };

    var newMobileWorkerModel = function(options) {
        var self = mobileWorkerModel(options);

        self.creationStatus = ko.observable('');

        self.isPending = ko.computed(function() { return self.creationStatus() === STATUS.PENDING; });
        self.isSuccess = ko.computed(function() { return self.creationStatus() === STATUS.SUCCESS; });
        self.isWarning = ko.computed(function() { return self.creationStatus() === STATUS.WARNING; });

        return self;
    };

    var mobileWorkersListModel = function() {
        var self = {};

        self.users = ko.observableArray([]);
        self.query = ko.observable('');
        self.inactiveOnly = ko.observable(false);

        // Pagination
        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable();

        // Visibility of spinner, messages, and user table
        self.hasError = ko.observable(false);
        self.notLoaded = ko.observable(true);
        self.projectHasUsers = ko.observable(true);

        self.showProjectHasNoUsers = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.projectHasUsers();
        });

        self.showNoUsers = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.totalItems() && !self.showProjectHasNoUsers();
        });

        self.showSpinner = ko.computed(function() {
            return self.notLoaded() && !self.hasError();
        });

        self.showTable = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.showNoUsers() && !self.showProjectHasNoUsers();
        });

        self.toggleInactiveOnly = function(inactiveOnly) {
            self.inactiveOnly(inactiveOnly);
            self.goToPage(1);
        };

        self.goToPage = function(page) {
            self.users.removeAll();

            self.hasError(false);
            self.notLoaded(true);
            $.ajax({
                method: 'GET',
                url: hqImport("hqwebapp/js/initial_page_data").reverse('paginate_mobile_workers'),
                data: {
                    page: page || 1,
                    query: self.query(),
                    limit: self.itemsPerPage(),
                    showDeactivatedUsers: self.inactiveOnly() ? 1 : 0,
                },
                success: function(data) {
                    self.totalItems(data.total);
                    self.users.removeAll();     // just in case there are multiple goToPage calls simultaneously
                    _.each(data.users, function(user) {
                        self.users.push(mobileWorkerModel(user));
                    });

                    if (!self.query()) {
                        self.projectHasUsers(!!data.users.length);
                    }
                    self.notLoaded(false);
                    self.hasError(false);
                },
                error: function() {
                    self.notLoaded(false);
                    self.hasError(true);
               },
            });
        };

        self.goToPage(1);

        return self;
    }

    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
        RETRIED: 'retried',
    };
    var USERNAME_STATUS = {
        PENDING: 'pending',
        TAKEN: 'taken',
        AVAILABLE: 'available',
        AVAILABLE_WARNING: 'warning',
        ERROR: 'error',
    };

    var newMobileWorkersListModel = function() {
        var self = {};

        self.users = ko.observableArray([]);
        self.hasUsers = ko.computed(function() {
            return self.users().length;
        });

        self.mobileWorker = newMobileWorkerModel();  // new worker being added
        self.mobileWorker.clear();
        self.initializeMobileWorker = function() {
            self.mobileWorker.clear();
            hqImport('analytix/js/google').track.event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        self.allowMobileWorkerCreation = ko.computed(function() {
            // TODO: mobileWorkerForm.$invalid || usernameAvailabilityStatus !== 'available'
            return true;
        });

        self.submitNewMobileWorker = function() {
            $("#newMobileWorkerModal").modal('hide');
            var newWorker = _.clone(self.mobileWorker);
            self.users.push(newWorker);
            newWorker.creationStatus(STATUS.PENDING);

            var deferred = $.Deferred();
            // TODO
            /*if (typeof(hex_parser) !== 'undefined') {
                newWorker.password = (new hex_parser()).encode(newWorker.password);
            }*/

            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse("create_mobile_worker"),
                data: {
                    username: newWorker.username(),
                    password: newWorker.password(),
                    customFields: newWorker.customFields,
                    first_name: newWorker.first_name(),
                    last_name: newWorker.first_name(),
                    location: newWorker.location(),
                },
                success: function(data) {
                    if (data.success) {
                        newWorker.creationStatus(STATUS.SUCCESS);
                        newWorker.editUrl(data.editUrl);    // TODO: test
                        deferred.resolve(data);
                    } else {
                        newWorker.creationStatus(STATUS.WARNING);
                        deferred.reject(data);
                    }
                },
                error: function(data) {
                    // TODO: test
                    newWorker.creationStatus(STATUS.WARNING);
                    deferred.reject(
                        gettext("Sorry, there was an issue communicating with the server.")
                    );
                },
            });
        };

        self.retryMobileWorker = function() {
            console.log("do something");
        };

        return self;
    };

    $(function() {
        var mobileWorkersList = mobileWorkersListModel(),
            newMobileWorkersList = newMobileWorkersListModel();
        $("#mobile-workers-list").koApplyBindings(mobileWorkersList);
        $("#new-mobile-workers-list").koApplyBindings(newMobileWorkersList);
        $("#newMobileWorkerModal").koApplyBindings(newMobileWorkersList);
        $("#newMobileWorkerModalTrigger").koApplyBindings(newMobileWorkersList);
    });
});
