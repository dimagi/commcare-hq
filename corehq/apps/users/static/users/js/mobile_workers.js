hqDefine("users/js/mobile_workers", function() {
    var mobileWorkersList = function() {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable(''); // TODO

        // Visibility of spinner, messages, and user table
        self.hasError = ko.observable(false);
        self.notLoaded = ko.observable(true);
        self.projectHasUsers = ko.observable(true);

        self.showProjectHasNoUsers = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.projectHasUsers();
        });

        self.showNoUsers = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.users().length && !self.showProjectHasNoUsers();
        });

        self.showSpinner = ko.computed(function() {
            return self.notLoaded() && !self.hasError();
        });

        self.showTable = ko.computed(function() {
            return !self.notLoaded() && !self.hasError() && !self.showNoUsers() && !self.showProjectHasNoUsers();
        });

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
                    limit: 10,  // TODO
                },
                success: function(data) {
                    self.users.removeAll();     // just in case there are multiple goToPage calls simultaneously
                    _.each(data.users, function(user) {
                        self.users.push(user);
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
