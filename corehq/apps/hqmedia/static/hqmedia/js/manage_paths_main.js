hqDefine("hqmedia/js/manage_paths_main", function () {
    var uploadPathsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['url']);
        var self = options;

        // Messaging
        self.genericErrorMessage = gettext("There was an error processing your file. Please try again or report an issue if the problem persists.");
        self.serverError = ko.observable('');
        self.errorMessages = ko.observableArray();
        self.warningMessages = ko.observableArray();
        self.successMessage = ko.observable('');
        self.successMessages = ko.observableArray();
        self.isSubmitting = ko.observable(false);

        self.clearMessages = function () {
            self.serverError('');
            self.errorMessages.removeAll();
            self.warningMessages.removeAll();
            self.successMessage('');
            self.successMessages.removeAll();
        };

        self.update = function (form) {
            self.isSubmitting(true);
            self.clearMessages();
            $.ajax({
                method: 'POST',
                url: self.url,
                data: new FormData(form),
                processData: false,
                contentType: false,
                success: function (data) {
                    self.isSubmitting(false);
                    if (data.complete) {
                        self.errorMessages(data.errors || []);
                        if (self.errorMessages().length) {
                            return;
                        }

                        self.warningMessages(data.warnings);
                        self.successMessages(data.successes);
                        if (!self.successMessages().length) {
                            self.successMessage(gettext("No items were found to update."));
                        }
                    } else {
                        self.serverError(data.error || self.genericErrorMessage);
                    }
                },
                error: function () {
                    self.isSubmitting(false);
                    self.serverError(self.genericErrorMessage);
                },
            });
        };

        return self;
    };

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        $("#upload-paths").koApplyBindings(uploadPathsModel({
            url: initialPageData.reverse("update_multimedia_paths"),
        }));
    });
});
