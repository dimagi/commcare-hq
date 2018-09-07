hqDefine('case_importer/js/import_history', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/components.ko',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var uploadModel = function (options) {
        var self = _.extend({}, _.omit(options, 'comment', 'task_status'));

        self.comment = ko.observable(options.comment || '');
        self.task_status = ko.observable(options.task_status);

        self.commentUrl = function () {
            return initialPageData.reverse('case_importer_update_upload_comment', self.upload_id);
        };

        self.downloadUrl = function () {
            return initialPageData.reverse('case_importer_upload_file_download', self.upload_id);
        };

        return self;
    };

    var recentUploads = function () {
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
                _.chain(self.case_uploads()).pluck('task_status').map(function (taskStatus) {
                    return taskStatus();
                }).isEqual(_(data).pluck('task_status').map(function (taskStatus) {
                    return taskStatus();
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
                        var caseUpload = pair[0];
                        var newCaseUpload = pair[1];
                        if (caseUpload.upload_id !== newCaseUpload.upload_id) {
                            throw new Error("Somehow even after checking, the case upload lists didn't line up.");
                        }
                        caseUpload.task_status(newCaseUpload.task_status());
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
            $.get(initialPageData.reverse('case_importer_uploads'), {limit: initialPageData.getUrlParameter('limit')}).done(function (data) {
                self.state(self.states.SUCCESS);
                data = _.map(data, function (caseUpload) {
                    return uploadModel(caseUpload);
                });
                self.updateCaseUploads(data);

                var anyInProgress = _.any(self.case_uploads(), function (caseUpload) {
                    return caseUpload.task_status().state === self.states.STARTED ||
                            caseUpload.task_status().state === self.states.NOT_STARTED;
                });
                if (anyInProgress) {
                    _.delay(self.fetchCaseUploads, 5000);
                }
            }).fail(function () {
                self.state(self.states.FAILED);
            });
        };
        return self;
    };

    return {
        recentUploadsModel: recentUploads,
    };
});
