hqDefine("hqmedia/js/manage_paths_main", function () {
    var uploadPathsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['validateUrl', 'updateUrl']);
        var self = options;

        self.validated = ko.observable(false);
        self.fileId = ko.observable();

        self.genericError = gettext("There was an error processing your file. Please try again or report an issue if the problem persists.");
        self.error = ko.observable();

        self.allowUpdate = ko.computed(function () {
            return self.validated() && !self.error();
        });

        self.validate = function (form) {
            // TODO: spinner behavior
            self.validated(false);
            $.ajax({
                method: 'POST',
                url: self.validateUrl,
                data: new FormData(form),
                processData: false,
                contentType: false,
                success: function (data) {
                    if (data.success) {
                        self.fileId(data.file_id);
                        self.validated(true);
                        self.error('');

                        console.log("TODO: validation successful, show output");
                        console.log("Got file " + self.fileId());
                    } else {
                        self.error(data.error || self.genericError)
                    }
                },
                error: function () {
                    self.error(self.genericError);
                },
            });

            return false;
        };

        self.update = function () {
            // TODO: spinner behavior
            $.ajax({
                method: 'POST',
                url: self.updateUrl,
                data: {
                    file_id: self.fileId(),
                },
                success: function (data) {
                    if (data.success) {
                        console.log("TODO: update successful, show output");
                        self.error('');
                    } else {
                        self.error(data.error || self.genericError);
                    }
                },
                error: function () {
                    self.error(self.genericError);
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
