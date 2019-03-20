hqDefine('case_importer/js/import_history', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/components.ko',
], function (
    $,
    ko,
    _,
    assertProperties,
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

        self.formIdsUrl = function () {
            return initialPageData.reverse('case_importer_upload_form_ids', self.upload_id);
        };

        self.caseIdsUrl = function () {
            return initialPageData.reverse('case_importer_upload_case_ids', self.upload_id);
        };

        return self;
    };

    var recentUploads = function (options) {
        assertProperties.assertRequired(options, ['totalItems']);

        var self = {};
        self.totalItems = ko.observable(options.totalItems);
        self.itemsPerPage = ko.observable();
        self.showPaginationSpinner = ko.observable(false);
        self.currentPage = ko.observable();
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
        self.state = ko.observable(self.states.MISSING);
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
        self.goToPage = function (page) {
            if (self.state() === self.states.MISSING) {
                // only show spinner on first fetch
                self.state(self.states.STARTED);
            }
            self.showPaginationSpinner(true);
            $.get(initialPageData.reverse('case_importer_uploads'), {
                page: page,
                limit: self.itemsPerPage(),
            }).done(function (data) {
                self.showPaginationSpinner(false);
                self.state(self.states.SUCCESS);
                data = _.map(data, function (caseUpload) {
                    return uploadModel(caseUpload);
                });
                self.updateCaseUploads(data);

                var anyInProgress = _.any(self.case_uploads(), function (caseUpload) {
                    return caseUpload.task_status().state === self.states.STARTED ||
                            caseUpload.task_status().state === self.states.MISSING;
                });

                // If there's work in progress, try refreshing this page in a few seconds
                if (anyInProgress) {
                    _.delay(function () {
                        if (page === self.currentPage()) {
                            self.goToPage(page);
                        }
                    }, 5000);
                }
                self.currentPage(page);
            }).fail(function () {
                self.showPaginationSpinner(false);
                self.state(self.states.FAILED);
            });
        };
        return self;
    };

    return {
        recentUploadsModel: recentUploads,
    };
});
