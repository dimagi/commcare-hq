hqDefine("users/js/enterprise_users",[
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/initial_page_data",
    'hqwebapp/js/components.ko',    // pagination and search box widgets
], function ($, ko, _, assertProperties, initialPageData) {
    var webUsersList = function () {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');

        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.error = ko.observable();
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.showUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.error() && self.users().length > 0;
        });

        self.noUsersMessage = ko.computed(function () {
            if (!self.showLoadingSpinner() && !self.error() && self.users().length === 0) {
                if (self.query()) {
                    return gettext("No users matched your search.");
                }
                return gettext("This project has no web users. Please invite a web user above.");
            }
            return "";
        });

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            self.error('');
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('paginate_enterprise_users'),
                data: {
                    page: page,
                    query: self.query() || '',
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.totalItems(data.total);
                    self.users.removeAll();
                    _.each(data.users, function (user) {
                        self.users.push(user);
                    });
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.error(gettext("Could not load users. Please try again later or report an issue if this problem persists."));
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $(function () {
        $("#web-users-panel").koApplyBindings(webUsersList());
    });
});
