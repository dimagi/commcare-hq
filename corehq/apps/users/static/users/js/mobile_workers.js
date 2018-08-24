hqDefine("users/js/mobile_workers", function() {
    var mobileWorker = function(options) {
        var self = ko.mapping.fromJS(options);

        self.mark_activated = ko.observable(false);
        self.mark_deactivated = ko.observable(false);
        self.action_error = ko.observable('');

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

    var mobileWorkersList = function() {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');
        self.inactiveOnly = ko.observable(false);

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
                        self.users.push(mobileWorker(user));
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
    };

    $(function() {
        $("#mobile-workers-list").koApplyBindings(mobileWorkersList());
    });
});
