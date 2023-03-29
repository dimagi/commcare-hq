hqDefine("events/js/event_attendees",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    'jquery.rmi/jquery.rmi',
    "hqwebapp/js/widgets",
    "hqwebapp/js/components.ko", // for pagination
], function (
    $,
    ko,
    _,
    initialPageData,
    RMI
) {
    'use strict';

    var STATUS_CSS = {
        NONE: '',
        PENDING: 'pending',
        SUCCESS: 'success',
        WARNING: 'warning',
        ERROR: 'danger',
        DISABLED: 'disabled',
    };

    var rmi = function () {};  // Defined below

    var attendeeModel = function (options) {
        options = options || {};
        options = _.defaults(options, {
            creationStatus: STATUS_CSS.NONE,
            creationError: '',
            name: '',
            case_id: '',
        });

        var self = ko.mapping.fromJS(options);
        return self;
    };

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
                    self.attendees(_.map(data.attendees, function (attendee) {
                        return attendeeModel(attendee);
                    }));

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

    var newAttendeeCreationModel = function () {
        var self = {};

        // Make status constants available to bindings in HTML
        self.STATUS_CSS = STATUS_CSS;

        // Attendee in new attendee modal, not yet sent to server
        self.stagedAttendee = ko.observable();

        // New attendees sent to server
        self.newAttendees = ko.observableArray();

        self.allowSubmit = ko.computed(function () {
            return !!(self.stagedAttendee() && self.stagedAttendee().name());
        });

        self.initializeAttendee = function () {
            self.stagedAttendee(attendeeModel({}));
        };

        self.submitNewAttendee = function () {
            $("#new-attendee-modal").modal('hide');
            //var newAttendee = ko.mapping.toJS(self.stagedAttendee);
            var newAttendee = attendeeModel(ko.mapping.toJS(self.stagedAttendee));
            self.newAttendees.push(newAttendee);
            newAttendee.creationStatus(STATUS_CSS.PENDING);

            rmi('create_attendee', {
                attendee: ko.mapping.toJS(newAttendee),
            }).done(function (data) {
                if (data.success) {
                    newAttendee.case_id(data.case_id);
                    newAttendee.creationStatus(STATUS_CSS.SUCCESS);
                } else {
                    newAttendee.creationStatus(STATUS_CSS.ERROR);
                    if (data.error) {
                        newAttendee.creationError(data.error);
                    }
                }
            }).fail(function () {
                newAttendee.creationStatus(STATUS_CSS.ERROR);
            });
        };

        return self;
    };

    $(function () {
        var rmiInvoker = RMI(
            initialPageData.reverse('event_attendees'),
            $("#csrfTokenContainer").val()
        );
        rmi = function (remoteMethod, data) {
            return rmiInvoker("", data, {
                headers: {"DjNg-Remote-Method": remoteMethod},
            });
        };

        $("#attendees-list").koApplyBindings(attendeesListModel());

        var newAttendeeCreation = newAttendeeCreationModel();
        $("#attendee-actions").koApplyBindings(newAttendeeCreation, mobileWorkerAttendees());
        $("#new-attendee-modal").koApplyBindings(newAttendeeCreation);
        $("#new-attendees-list").koApplyBindings(newAttendeeCreation);
    });
});
