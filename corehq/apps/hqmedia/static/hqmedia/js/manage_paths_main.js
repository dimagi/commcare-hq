hqDefine("hqmedia/js/manage_paths_main", function () {
    var uploadPathsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['validateUrl', 'updateUrl']);
        var self = options;

        self.fileId = ko.observable('');

        self.genericErrorMessage = gettext("There was an error processing your file. Please try again or report an issue if the problem persists.");
        self.serverError = ko.observable('');
        self.errorMessages = ko.observableArray();
        self.warningMessages = ko.observableArray();
        self.successMessage = ko.observable('');

        self.allowUpdate = ko.computed(function () {
            return self.fileId() && !self.serverError() && !self.errorMessages().length;
        });

        self.clearMessages = function () {
            self.serverError('');
            self.errorMessages.removeAll();
            self.warningMessages.removeAll();
            self.successMessage('');
        };

        self.validate = function (form) {
            // TODO: spinner behavior
            self.clearMessages();
            $.ajax({
                method: 'POST',
                url: self.validateUrl,
                data: new FormData(form),
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {     // file was uploaded successfully, though its content may have errors
                        self.fileId(data.file_id);
                        self.errorMessages(data.errors);
                        self.warningMessages(data.warnings);
                        if (!self.errorMessages().length && !self.warningMessages().length) {
                            self.successMessage(gettext("File validated with no errors or warnings."));
                        }
                    } else {
                        self.serverError(data.error || self.genericError)
                    }
                },
                error: function () {
                    self.serverError(self.genericError);
                },
            });

            return false;
        };

        self.update = function () {
            // TODO: spinner behavior
            self.clearMessages();
            $.ajax({
                method: 'POST',
                url: self.updateUrl,
                data: {
                    file_id: self.fileId(),
                },
                success: function (data) {
                    if (data.success) {
                        console.log("TODO: update successful, show output");
                    } else {
                        self.serverError(data.error || self.genericError);
                    }
                },
                error: function () {
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
