/*

    ScheduledReportModel - model representing a single row on the list / a single report filter file
    ScheduleReportPanelModel - model representing a whole table ('My Scheduled Reports' and 'Other Scheduled Reports')
    ScheduledReportListModel - model representing the whole page (list of reports, actions)

*/

hqDefine("reports/js/scheduled_reports_list", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/bootstrap3/components.ko', // pagination & feedback widget
], function (
    $,
    ko,
    _,
    assertProperties
) {
    "use strict";
    var scheduledReportModel = function (report, isOwner, isAdmin) {
        assertProperties.assert(report, [
            'id',
            'addedToBulk',
            'domain',
            'owner_id',
            'recipient_emails',
            'config_ids',
            'send_to_owner',
            'hour',
            'minute',
            'day',
            'uuid',
            'start_date',
            'configs',
            'is_editable',
            'owner_email',
            'day_name',
            'editUrl',
            'viewUrl',
            'sendUrl',
            'deleteUrl',
            'unsubscribeUrl',
        ]);

        var self = ko.mapping.fromJS(report);

        self.configMany = true;
        if (report.configs.length === 1) {
            self.configMany = false;
        }

        self.recipient_email_count = self.recipient_emails().length;

        self.deleteScheduledReport = function (observable, event) {
            $(event.currentTarget).closest('form').submit();
        };

        self.is_owner = isOwner;
        self.is_admin = isAdmin;
        self.firstConfig = ko.observable(report.configs[0]);

        return self;
    };

    var scheduledReportsPanelModel = function (options) {
        assertProperties.assert(options, ['reports', 'is_owner', 'is_admin', 'header']);

        var self = _.extend({}, options);

        self.scheduledReports = ko.observableArray();
        self.items = ko.observableArray();
        self.isLoadingPanel = ko.observable(true);
        self.perPage = ko.observable();

        self.scheduledReports(ko.utils.arrayMap(options.reports, function (report) {
            return scheduledReportModel(report, self.is_owner, self.is_admin);
        }));

        self.goToPage = function (page) {
            self.isLoadingPanel(true);
            self.items(self.scheduledReports.slice(self.perPage() * (page - 1), self.perPage() * page));
            self.isLoadingPanel(false);
        };

        self.selectAll = function () {
            _.each(self.items(), function (e) { e.addedToBulk(true); });
        };

        self.selectNone = function () {
            _.each(self.items(), function (e) { e.addedToBulk(false); });
        };

        self.totalItems = ko.observable(self.scheduledReports().length);

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    var scheduledReportListModel = function (options) {
        assertProperties.assert(options, ['scheduled_reports', 'other_scheduled_reports', 'is_admin']);

        var self = {};
        window.scrollTo(0, 0);

        self.bulkAction = ko.observable(false);
        self.isBulkDeleting = ko.observable(false);
        self.isBulkSending = ko.observable(false);
        self.action = ko.observable();

        self.panels = ko.observableArray([]);
        self.panels.push(scheduledReportsPanelModel({
            reports: options.scheduled_reports,
            is_owner: true,
            is_admin: options.is_admin,
            header: gettext("My Scheduled Reports"),
        }));
        self.panels.push(scheduledReportsPanelModel({
            reports: options.other_scheduled_reports,
            is_owner: false,
            is_admin: options.is_admin,
            header: gettext("Other Scheduled Reports"),
        }));

        self.reports = ko.computed(function () {
            return _.flatten(_.map(self.panels(), function (panel) { return panel.scheduledReports(); }));
        });

        self.selectedReports = ko.computed(function () {
            return _.filter(self.reports(), function (e) { return e.addedToBulk(); });
        });

        self.selectedReportsCount = ko.computed(function () {
            return self.selectedReports().length;
        });

        self.isMultiple = ko.computed(function () {
            if (self.selectedReportsCount() > 1) {
                return true;
            }
            return false;
        });

        self.sendModal = function () {
            self.action('send');
        };

        self.deleteModal = function () {
            self.action('delete');
        };

        self.bulkSend = function () {
            self.bulkAction(true);
            self.isBulkSending(true);
            var sendList = _.filter(self.reports(), function (e) {return e.addedToBulk();});
            var ids = [];
            for (let i = 0; i < sendList.length; i++) {
                ids.push(sendList[i].id());
            }
            ids = JSON.stringify(ids);
            $.ajax({
                method: 'POST',
                url: sendList[0].sendUrl(),
                data: {
                    "sendList": ids,
                    "bulkSendCount": sendList.length,
                },
                success: function () {
                    location.reload();
                },
            });
        };

        self.bulkDelete = function () {
            self.bulkAction(true);
            self.isBulkDeleting(true);
            var deleteList = _.filter(self.reports(), function (e) {return e.addedToBulk();});
            var ids = [];
            for (let i = 0; i < deleteList.length; i++) {
                ids.push(deleteList[i].id());
            }
            ids = JSON.stringify(ids);
            $.ajax({
                method: 'POST',
                url: deleteList[0].deleteUrl(),
                data: {
                    "deleteList": ids,
                    "bulkDeleteCount": deleteList.length,
                },
                success: function () {
                    location.reload();
                },
            });
        };

        return self;
    };

    return {
        scheduledReportListModel: scheduledReportListModel,
    };

});


