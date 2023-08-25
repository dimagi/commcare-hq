/**
 * This file controls the UI for the enterprise users page.
 * This page is based on the main "Current Users" panel on
 * the web users page, but it displays a different set of columns
 * and adds in rows for mobile workers linked to the web users.
 */
hqDefine("users/js/enterprise_users", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "users/js/web_users_list",
    "hqwebapp/js/bootstrap3/components.ko",    // pagination and search box widgets
], function (
    $,
    ko,
    _,
    initialPageData,
    webUsersList
) {
    var UserModel = function (options) {
        var self = _.defaults(options, {
            profile: null,
            loginAsUser: null,
            loginAsUserCount: 0,
            inactiveMobileCount: 0,
        });

        // Only varies for mobile users
        self.visible = ko.observable(!self.loginAsUser);

        // Only relevant for web users
        self.expanded = ko.observable(false);


        return self;
    };

    var enterpriseUsersList = function (options) {

        var self = webUsersList(options);

        self.toggleLoginAsUsers = function (webUser) {
            webUser.expanded(!webUser.expanded());
            _.each(self.users(), function (user) {
                if (user.loginAsUser === webUser.username) {
                    user.visible(webUser.expanded() && user.is_active !== self.showDeactivated());
                }
            });
        };

        self.showDeactivated = ko.observable(false);

        self.toggleDeactivatedText = ko.computed(function () {
            return self.showDeactivated() ? gettext("Hide Deactivated Mobile Workers") : gettext("Show Deactivated Mobile Workers");
        });

        self.toggleDeactivated = function () {
            _.each(self.users(), function (user) {
                if (!user.loginAsUser) {
                    user.expanded(false);
                    if (self.showDeactivated()) {
                        user.visible(user.inactiveMobileCount > 0);
                    } else {
                        user.visible(true);
                    }
                } else {
                    user.visible(false);
                }
            });
        };

        self.showDeactivated.subscribe(function () {
            self.toggleDeactivated();
        });

        self.sortBy = ko.observable('');

        self.ascending = ko.observable(false);

        self.sortByColumn = function (data, event) {
            var el = event.target;
            var column = el.getAttribute('data-name');
            var webUsers = [];
            var mobileWorkersMap = {};
            var allSortedUsers = [];
            // Change target el icon depending on self.ascending() and revert all other icons
            var resetColumnIcons = function (ascending) {
                var allColumns = $('.sort-icon');
                allColumns.removeClass('glyphicon-sort-by-attributes glyphicon-sort-by-attributes-alt');
                allColumns.addClass('glyphicon-sort');
                $(el).addClass(ascending ? 'glyphicon-sort-by-attributes' : 'glyphicon-sort-by-attributes-alt');
            };

            var columnSort = function (userArr, ascending) {
                resetColumnIcons(ascending);
                userArr.sort(function (a, b) {
                    if (!a[column]) {
                        return 1;
                    }
                    if (!b[column]) {
                        return -1;
                    }

                    return ascending ? a[column].localeCompare(b[column]) : b[column].localeCompare(a[column]);
                });

                return userArr;
            };

            // Map mobile workers to web users to maintain ordering
            _.each(data.users(), function (user) {
                if (!user.loginAsUser) {
                    webUsers.push(user);
                } else {
                    if (!mobileWorkersMap[user.loginAsUser]) {
                        mobileWorkersMap[user.loginAsUser] = [user];
                    } else {
                        mobileWorkersMap[user.loginAsUser].push(user);
                    }
                }
            });

            self.ascending(column !== self.sortBy());

            self.sortBy(column === self.sortBy() ? '' : column);

            columnSort(webUsers, self.ascending());

            // Update observable array with sorted web and associated mobile users
            _.each(webUsers, function (user) {
                allSortedUsers.push(user);
                var sortedMobileWorkers = columnSort(mobileWorkersMap[user.username], self.ascending());
                allSortedUsers = allSortedUsers.concat(sortedMobileWorkers);
            });

            data.users(allSortedUsers);
        };

        return self;
    };

    $(function () {
        $("#web-users-panel").koApplyBindings(enterpriseUsersList({
            url: initialPageData.reverse("paginate_enterprise_users"),
            userModel: UserModel,
        }));
    });
});
