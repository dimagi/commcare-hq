hqDefine('case_importer/js/import_history', function () {
    var urllib = hqImport('hqwebapp/js/urllib');
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
        var uploadIdsInDataMatchCurrent = function (data) {
            return _.chain(self.case_uploads()).pluck('upload_id').isEqual(_(data).pluck('upload_id')).value();
        };
        var taskStatusesInDataMatchCurrent = function (data) {
            return (
                _.chain(self.case_uploads()).pluck('task_status').map(function (task_status) {
                    return task_status();
                }).isEqual(_(data).pluck('task_status').map(function (task_status) {
                    return task_status();
                })).value()
            );
        };
        self.updateCaseUploads = function (data) {
            if (!uploadIdsInDataMatchCurrent(data) || !taskStatusesInDataMatchCurrent(data)) {
                if (uploadIdsInDataMatchCurrent(data)) {
                    // in the easy case, update just the essential information (task_status) in place
                    // this prevents some jumpiness when not necessary
                    // and is particularly bad if you're in the middle of editing a comment
                    _.each(_.zip(self.case_uploads(), data), function (pair) {
                        var case_upload = pair[0];
                        var new_case_upload = pair[1];
                        if (case_upload.upload_id !== new_case_upload.upload_id) {
                            throw {message: "Somehow even after checking, the case upload lists didn't line up."};
                        }
                        case_upload.task_status(new_case_upload.task_status());
                    });
                } else {
                    self.case_uploads(data);
                }
            }
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
                    case_upload.task_status = ko.observable(case_upload.task_status);
                });
                self.updateCaseUploads(data);

                var anyInProgress = _.any(self.case_uploads(), function (case_upload) {
                    return case_upload.task_status().state === self.states.STARTED ||
                            case_upload.task_status().state === self.states.NOT_STARTED;
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
