hqDefine("events/js/event_attendees",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/widgets",
    "hqwebapp/js/components.ko",

], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';
    var attendeesListModel = function () {
        var self = {};
        self.attendees = ko.observableArray([]);

        self.query = ko.observable('');
        self.deactivatedOnly = ko.observable(false);

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable();

        // Visibility of spinners, messages, and attendees table
        self.hasError = ko.observable(false);
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.projectHasAttendees = ko.observable(true);

        self.showProjectHasNoAttendees = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.projectHasAttendees();
        });

        self.showNoAttendees = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.totalItems() && !self.showProjectHasNoAttendees();
        });

        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.showNoAttendees() && !self.showProjectHasNoAttendees();
        });

        self.goToPage = function (page) {
            self.attendees.removeAll();
            self.hasError(false);
            self.showPaginationSpinner(true);
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('paginated_attendees'),
                data: {
                    page: page || 1,
                    query: self.query(),
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.totalItems(data.total);
                    self.attendees(data.attendees);

                    if (!self.query()) {
                        self.projectHasAttendees(!!data.attendees.length);
                    } else {
                        self.projectHasAttendees(true);
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

    var mobileWorkerAttendees = function() {
        self.mobileWorkerAttendeesEnabled = ko.observable(false);

        self.toggleMobileWorkerAttendees = function() {
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('attendees_config'),
                contentType: 'application/json',
                data: JSON.stringify({'mobile_worker_attendee_enabled': !self.mobileWorkerAttendeesEnabled()}),
                success: function (data) {
                    self.mobileWorkerAttendeesEnabled(data.mobile_worker_attendee_enabled);
                },
            });
        };

        self.loadMobileWorkerAttendeeConfig = function() {
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('attendees_config'),
                success: function (data) {
                    self.mobileWorkerAttendeesEnabled(data.mobile_worker_attendee_enabled);
                },
            });
        };
        self.loadMobileWorkerAttendeeConfig();
        return self;
    };

    $(function () {
        $("#attendees-list").koApplyBindings(attendeesListModel());
        $("#mobile-worker-attendees").koApplyBindings(mobileWorkerAttendees());
    });
});
