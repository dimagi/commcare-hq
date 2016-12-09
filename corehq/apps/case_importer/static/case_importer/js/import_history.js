hqDefine('case_importer/js/import_history.js', function () {
    var urllib = hqImport('hqwebapp/js/urllib.js');
    function RecentUploads() {
        var self = {};
        // this is used both for the state of the ajax request
        // and for the state of celery task
        self.states = {
            NOT_STARTED: 0,
            STARTED: 1,
            SUCCESS: 2,
            FAILED: 3,
        };
        self.case_uploads = ko.observableArray(null);
        self.state = ko.observable(self.states.NOT_STARTED);
        self.fetchCaseUploads = function () {
            if (self.state() === self.states.NOT_STARTED) {
                // only show spinner on first fetch
                self.state(self.states.STARTED);
            }
            $.get(urllib.reverse('case_importer_uploads'), {limit: urllib.getUrlParameter('limit')}).success(function (data) {
                self.state(self.states.SUCCESS);
                self.case_uploads(data);
                var anyInProgress = _.any(self.case_uploads(), function (case_upload) {
                    return case_upload.task_status.state === self.states.STARTED ||
                            case_upload.task_status.state === self.states.NOT_STARTED;
                });
                if (anyInProgress) {
                    _.delay(self.fetchCaseUploads, 5000);
                }
            }).error(function () {
                self.state(self.states.FAILED);
            });
        };
        return self;
    }
    return {
        RecentUploads: RecentUploads
    };
});
