hqDefine('data_management/js/data_management', [
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'hqwebapp/js/components.ko',    // pagination widget
    'hqwebapp/js/knockout_bindings.ko', // for modals
    'jquery-ui/ui/datepicker',
], function ($, ko, _, initialPageData) {
    'use strict';

    var dataManagementRequest = function (name, dbAlias, createdAt, initiatedBy, startedOn, endedOn, startDate,
        endDate, status, statusText, error) {
        var self = {};
        self.name = name;
        self.dbAlias = dbAlias;
        self.initiatedBy = initiatedBy + gettext(' On ') + createdAt;
        self.startedOn = startedOn;
        self.endedOn = endedOn;
        if (startDate) {
            self.dateRange = startDate + '-' + endDate;
        } else {
            self.dateRange = '';
        }
        self.statusText = statusText;
        if (status === 3) {
            self.statusText += '(' + error + ')';
        }
        return self;
    };

    var requestsList = function () {
        var self = {};
        self.requests = ko.observableArray([]);

        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.error = ko.observable();
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.showRequests = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.error() && self.requests().length > 0;
        });

        self.noRequestsMessage = ko.computed(function () {
            if (!self.showLoadingSpinner() && !self.error() && self.requests().length === 0) {
                return gettext("This project has no data management requests.");
            }
            return "";
        });

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            self.error('');
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('paginate_data_management_requests'),
                data: {
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.totalItems(data.total);
                    self.requests.removeAll();
                    _.each(data.requests, function (request) {
                        self.requests.push(dataManagementRequest(
                            request.name, request.db_alias, request.created_at, request.initiated_by,
                            request.started_on, request.ended_on, request.start_date,
                            request.end_date, request.status, request.status_text, request.error));
                    });
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.error(gettext("Could not load requests. Please try again later or report an issue if this problem persists."));
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $(function () {
        $("#data-management-requests-panel").koApplyBindings(requestsList());
        $('.date-picker').datepicker({
            dateFormat: "yy-mm-dd",
            maxDate: 0,
        });
    });
});
