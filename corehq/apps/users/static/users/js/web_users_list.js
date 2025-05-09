/**
 * This file contains a knockout model for a list of web users with pagination and search.
 *
 * Options:
 *     url (required) - URL from which to fetch a page of users
 *     userModel (optional) - Knockout model in which to wrap each user
 */
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import assertProperties from "hqwebapp/js/assert_properties";
import "hqwebapp/js/components/pagination";
import "hqwebapp/js/components/search_box";

export default function (options) {
    assertProperties.assert(options, ["url"], ["userModel"]);

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
    self.showActiveUsers = ko.observable(true);
    self.showActiveUsers.subscribe(function (newValue) {
        self.goToPage(1);
    });

    self.noUsersMessage = ko.computed(function () {
        if (!self.showLoadingSpinner() && !self.error() && self.users().length === 0) {
            if (self.query()) {
                return gettext("No users matched your search.");
            }
            return gettext("This project has no web users.");
        }
        return "";
    });

    self.goToPage = function (page) {
        self.showPaginationSpinner(true);
        self.error('');
        $.ajax({
            method: 'GET',
            url: options.url,
            data: {
                page: page,
                query: self.query() || '',
                limit: self.itemsPerPage(),
                showActiveUsers: self.showActiveUsers()
            },
            success: function (data) {
                self.showLoadingSpinner(false);
                self.showPaginationSpinner(false);
                self.totalItems(data.total);
                self.users.removeAll();
                _.each(data.users, function (user) {
                    if (options.userModel) {
                        user = options.userModel(user);
                    }
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
}
