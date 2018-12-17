hqDefine("hqmedia/js/manage_paths_main", function () {
    var uploadPathsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['validateUrl', 'updateUrl']);
        var self = options;

        self.fileId = ko.observable('');

        // Messaging
        self.genericErrorMessage = gettext("There was an error processing your file. Please try again or report an issue if the problem persists.");
        self.serverError = ko.observable('');
        self.errorMessages = ko.observableArray();
        self.warningMessages = ko.observableArray();
        self.successMessage = ko.observable('');
        self.successMessages = ko.observableArray();

        // Controls for disabling, etc in UI
        self.isValidating = ko.observable(false);
        self.isUpdating = ko.observable(false);
        self.allowUpdate = ko.computed(function () {
            return self.fileId() && !self.serverError() && !self.errorMessages().length;
        });

        self.clearMessages = function () {
            self.serverError('');
            self.errorMessages.removeAll();
            self.warningMessages.removeAll();
            self.successMessage('');
            self.successMessages.removeAll();
        };

        self.validate = function (form) {
            self.clearMessages();
            self.isValidating(true);
            $.ajax({
                method: 'POST',
                url: self.validateUrl,
                data: new FormData(form),
                processData: false,
                contentType: false,
                success: function (data) {
                    self.isValidating(false);
                    if (data.success) {     // file was uploaded successfully, though its content may have errors
                        self.fileId(data.file_id);
                        self.errorMessages(data.errors);
                        self.warningMessages(data.warnings);
                        if (!self.errorMessages().length && !self.warningMessages().length) {
                            self.successMessage(gettext("File validated with no errors or warnings."));
                        }
                    } else {
                        self.serverError(data.error || self.genericError);
                    }
                },
                error: function () {
                    self.isValidating(false);
                    self.serverError(self.genericError);
                },
            });

            return false;
        };

        self.update = function () {
            self.isUpdating(true);
            self.clearMessages();
            $.ajax({
                method: 'POST',
                url: self.updateUrl,
                data: {
                    file_id: self.fileId(),
                },
                success: function (data) {
                    self.isUpdating(false);
                    if (data.success) {
                        if (!_.isEmpty(data.errors)) {
                            self.errorMessages(data.errors);
                        }

                        if (_.isEmpty(data.success_counts)) {
                            self.successMessage(gettext("No items were found to update."));
                        } else {
                            var messageTemplate = _.template(gettext("<%= count %> item(s) were updated in <%= link %>"));
                            self.successMessages(_.map(data.success_counts, function (count, id) {
                                return messageTemplate({
                                    count: data.success_counts[id],
                                    link: data.success_links[id],
                                });
                            }));
                        }
                    } else {
                        self.serverError(data.error || self.genericError);
                    }
                },
                error: function () {
                    self.isUpdating(false);
                    self.serverError(self.genericError);
                },
            });
        };

        return self;
    };

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        $("#upload-paths").koApplyBindings(uploadPathsModel({
            validateUrl: initialPageData.reverse("validate_multimedia_paths"),
            updateUrl: initialPageData.reverse("update_multimedia_paths"),
        }));
    });
});
