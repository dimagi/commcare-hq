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
    // These are used as css classes, so the values of success/warning/error need to be what they are.
    var STATUS = {
        NONE: '',
        PENDING: 'pending',
        SUCCESS: 'success',
        WARNING: 'warning',
        ERROR: 'danger',
        DISABLED: 'disabled',
    };
    var attendeeModel = function (options) {
        options = options || {};
        options = _.defaults(options, {
            creation_status: STATUS.NONE,
            creation_error: "",
            username: '',
            first_name: '',
            last_name: '',
            location_id: '',
            password: '',
            user_id: '',
            force_account_confirmation: false,
            email: '',
            send_account_confirmation_email: false,
            force_account_confirmation_by_sms: false,
            phone_number: '',
            is_active: true,
            is_account_confirmed: true,
            deactivate_after_date: '',
        });
        return options;
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

    $(function () {
        $("#attendees-list").koApplyBindings(attendeesListModel());
    });
});
