hqDefine('case_importer/js/import_history.js', function () {
    var urllib = hqImport('hqwebapp/js/urllib.js');
    function RecentUploads() {
        var self = {};
        // this is used both for the state of the ajax request
        // and for the state of celery task
        self.states = {
            MISSING: -1,
            NOT_STARTED: 0,
            STARTED: 1,
            SUCCESS: 2,
            FAILED: 3,
        };
        self.case_uploads = ko.observableArray(null);
        self.state = ko.observable(self.states.NOT_STARTED);
        var shouldUpdate = function (data) {
            // do not update DOM
            // if we're not either adding new uploads or updating the status
            // this prevents some jumpiness when not necessary
            // and is particularly bad if you're in the middle of editing a comment
            return !(_.chain(self.case_uploads()).pluck('upload_id').isEqual(_(data).pluck('upload_id')).value() &&
                _.chain(self.case_uploads()).pluck('task_status').isEqual(_(data).pluck('task_status')).value());
        };
        self.fetchCaseUploads = function () {
            if (self.state() === self.states.NOT_STARTED) {
                // only show spinner on first fetch
                self.state(self.states.STARTED);
            }
            $.get(urllib.reverse('case_importer_uploads'), {limit: urllib.getUrlParameter('limit')}).done(function (data) {
                self.state(self.states.SUCCESS);
                _(data).each(function (case_upload) {
                    case_upload.comment = ko.observable(case_upload.comment || '');
                });
                if (shouldUpdate(data)) {
                    self.case_uploads(data);
                }
                var anyInProgress = _.any(self.case_uploads(), function (case_upload) {
                    return case_upload.task_status.state === self.states.STARTED ||
                            case_upload.task_status.state === self.states.NOT_STARTED;
                });
                if (anyInProgress) {
                    _.delay(self.fetchCaseUploads, 5000);
                }
            }).fail(function () {
                self.state(self.states.FAILED);
            });
        };
        return self;
    }
    return {
        RecentUploads: RecentUploads,
    };
});
