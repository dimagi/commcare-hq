/*


    ScheduledReportModel - model representing a single row on the list / a single report filter file
    ScheduledReportListModel - model representing the whole page (list, modals, buttons)

*/

hqDefine("reports/js/scheduled_reports_list", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components.ko', // pagination & feedback widget

], function (
    $,
    ko,
    _,
) {

    var scheduledReportModel = function (data, isOwner, isAdmin) {

        var self = ko.mapping.fromJS(data);

        self.configMany = ko.computed(function() {
            if (data.configs.length === 1){
                return false
            };
            return true
        })

        self.recipient_email_count = ko.computed(function() {
            return self.recipient_emails().length;
        })

        self.deleteScheduledReport = function(observable, event){
            $(event.currentTarget).closest('form').submit();
        }
        self.is_owner = isOwner;
        self.is_admin = isAdmin

        return self;
    };

    var scheduledReportListModel = function (options) {

        var self = {};

        self.urls = options.urls;

        self.pageLoaded = ko.observable(false); //temp solution to hide unloaded page view

        self.scheduledReports = ko.observableArray([]);
        self.extraReports = ko.observableArray([]);

        /*
        self.goToPagePage = function (page) {
            self.pageLoaded(false);
            $.ajax({
                method: 'GET',
                url: self.urls.getPage,
                data: {
                    "nothing": "nothing",
                },
                success: function (stuff) {
                    self.pageLoaded(true);
                    console.log("it's working?")
                },
                error: function () {
                    console.log("failed lol");
                },
            });
        };
        */

        self.scheduledReports(ko.utils.arrayMap(options.scheduled_reports, function (report) {
            return scheduledReportModel(report, options.is_owner, options.is_admin);
        }));

        self.extraReports(ko.utils.arrayMap(options.extra_reports, function (report) {
            return scheduledReportModel(report);
        }));

        self.items = ko.observableArray();
        self.perPage = ko.observable();
        self.totalItems = ko.observable(self.scheduledReportsCount);

        self.selectAll = function () {
            _.each(self.scheduledReports(), function (e) { e.addedToBulk(true); });
        };

        self.selectNone = function () {
            _.each(self.scheduledReports(), function (e) { e.addedToBulk(false); });
        }

        self.selectedReportsCount = ko.computed(function () {
            return _.filter(self.scheduledReports(), function (e) { return e.addedToBulk(); }).length;
        });

        //replace w proper pagefetch ajax function
        self.goToPage = function(page) {
            self.items(self.scheduledReports.slice(self.perPage() * (page - 1), self.perPage() * page));
            self.pageLoaded(true);
        }

        self.bulkSend = function(){
            sendList = _.filter(self.scheduledReports(), function (e) {return e.addedToBulk()});
            ids = []
            for (let i = 0; i < sendList.length; i++) {
                ids.push(sendList[i].id())
            }
            ids = JSON.stringify(ids);
            $.ajax ({
                method: 'POST',
                url: sendList[0].sendUrl(),
                data: {"sendList": ids,
                       "bulk_send_count": sendList.length},
                success: function () {
                    location.reload()
                }
            });
        }

        self.bulkDelete = function(){
            deleteList = _.filter(self.scheduledReports(), function (e) {return e.addedToBulk()});
            ids = []
            for (let i = 0; i < deleteList.length; i++) {
                ids.push(deleteList[i].id())
            }
            ids = JSON.stringify(ids);
            $.ajax ({
                method: 'POST',
                url: deleteList[0].deleteUrl(),
                data: {"deleteList": ids,
                       "bulk_delete_count": deleteList.length},
                success: function () {
                    location.reload()
                }
            });
        }

        self.onPaginationLoad = function () {
            self.goToPage(1);
            //self.goToPagePage(1);
        };

        return self;
    };

    return {
        scheduledReportListModel: scheduledReportListModel,
    };

});


