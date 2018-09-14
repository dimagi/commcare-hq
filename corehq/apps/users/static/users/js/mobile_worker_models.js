hqDefine("users/js/mobile_worker_models", function() {
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
                location_id: null,
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
        self.last_name = ko.observable(options.first_name);
        self.phoneNumbers = ko.observableArray(options.phoneNumbers);
        self.user_id = ko.observable(options.user_id);
        self.location_id = ko.observable(options.location_id);
        self.dateRegistered = ko.observable(options.dateRegistered);
        self.editUrl = ko.observable(options.editUrl);
        self.action = ko.observable(options.action);
        self.mark_activated = ko.observable(options.mark_activated);
        self.mark_deactivated = ko.observable(options.mark_deactivated);
        self.action_error = ko.observable(options.action_error);

        // TODO: move to newMobileWorkerModel?
        self.clear = function() {
            self.username(defaults.username);
            self.password(defaults.password);
            self.customFields = defaults.customFields;
            self.first_name(defaults.first_name);
            self.last_name(defaults.last_name);
            self.phoneNumbers.removeAll();
            self.user_id(defaults.user_id);
            self.location_id(defaults.location_id);
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

    return {
        mobileWorkerModel: mobileWorkerModel,
        mobileWorkersListModel: mobileWorkersListModel,
    };
});
