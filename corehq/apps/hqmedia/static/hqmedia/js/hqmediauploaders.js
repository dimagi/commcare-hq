/* globals HQMediaUploaderTypes */
hqDefine("hqmedia/js/hqmediauploaders", function () {
    var HQMediaUploaders = {};  // This will be referenced by the media references
    const assertProperties = hqImport("hqwebapp/js/assert_properties"),
        initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
    _.each(initial_page_data("uploaders"), function (uploader) {
        HQMediaUploaders[uploader.slug] = new HQMediaUploaderTypes[uploader.uploader_type](
            uploader.slug,
            uploader.media_type,
            uploader.options
        );
        HQMediaUploaders[uploader.slug].init();
    });

    var get = function () {
        return HQMediaUploaders;
    };

    const uploader = function (slug, media_type, options) {
        assertProperties.assertRequired(options, [
            'uploadURL', 'uploadParams',
            'queueTemplate', 'errorsTemplate', 'existingFileTemplate',
        ]);

        var self = {};

        self.queueTemplate = options.queueTemplate;
        self.errorsTemplate = options.errorsTemplate;
        self.existingFileTemplate = options.existingFileTemplate;
        self.uploadParams = options.uploadParams;

        self.$container = $("#" + slug);
        self.$fileInputTrigger = self.$container.find(".hqm-select-files-container .btn-primary");
        self.$fileInput = self.$container.find(".hqm-select-files-container input[type='file']");
        self.$uploadStatusContainer = self.$container.find(".hqm-upload-status");
        self.$uploadButton = self.$container.find(".hqm-upload-confirm");
        self.uploadCompleteLabelSelector = ".hqm-upload-completed";
        self.$existingFile = self.$container.find(".hqm-existing");

        self.allowClose = true;

        self.updateUploadButton = function (enable, spin) {
            if (enable) {
                self.$uploadButton.removeClass('disabled');
            } else {
                self.$uploadButton.addClass('disabled');
            }
            if (spin) {
                self.$uploadButton.find(".fa-spin").removeClass("hide");
                self.$uploadButton.find(".fa-cloud-arrow-up").addClass("hide");
            } else {
                self.$uploadButton.find(".fa-spin").addClass("hide");
                self.$uploadButton.find(".fa-cloud-arrow-up").removeClass("hide");
            }
        };

        self.updateUploadFormUI = function () {
            self.$container.find(self.uploadCompleteLabelSelector).addClass('hide');

            if (self.currentReference.getUrl() && self.currentReference.isMediaMatched()) {
                self.$existingFile.removeClass('hide');
                self.$existingFile.find('.hqm-existing-controls').html(_.template(self.existingFileTemplate)({
                    url: self.currentReference.getUrl(),
                }));
            } else {
                self.$existingFile.addClass('hide');
                self.$existingFile.find('.hqm-existing-controls').empty();
            }
            $('.existing-media').tooltip({
                placement: 'bottom',
            });
        };

        self.init = function () {
            self.$container.on('show.bs.modal', function () {
                self.updateUploadFormUI();
            });

            // Don't allow user to close modal while server is processing upload
            var allowClose = true;
            self.$container.on('hide.bs.modal', function (event) {
                if (!self.allowClose) {
                    event.preventDefault();
                }
            });

            self.$fileInputTrigger.click(function () {
                self.$fileInput.click();
            });

            self.$fileInput.change(function () {
                var MEGABYTE = 1048576;

                if (self.$fileInput.get(0).files.length) {
                    var file = self.$fileInput.get(0).files[0];
                    self.$uploadStatusContainer.html(_.template(self.queueTemplate)({
                        file_size: (file.size / MEGABYTE).toFixed(3),
                        file_name: file.name,
                    }));
                    self.updateUploadButton(true, false);
                } else {
                    self.$uploadStatusContainer.empty();
                    self.updateUploadButton(false, false);
                }
            });

            self.$uploadButton.click(function () {
                event.preventDefault();

                self.updateUploadButton(false, true);
                self.allowClose = false;

                var file = self.$fileInput.get(0).files[0],
                    data = new FormData();
                data.append("Filedata", file);

                var newExtension = '.' + file.name.split('.').pop().toLowerCase();
                self.uploadParams.path = self.uploadParams.path.replace(/(\.[^/.]+)?$/, newExtension);
                _.each(self.uploadParams, function (value, key) {
                    data.append(key, value);
                });

                $.ajax({
                    url: options.uploadURL,
                    type: 'POST',
                    data: data,
                    contentType: false,
                    processData: false,
                    enctype: 'multipart/form-data',
                    success: function (response) {
                        response = JSON.parse(response);
                        $('[data-hqmediapath^="' + response.ref.path.replace(/\.\w+$/, ".") + '"]').trigger('mediaUploadComplete', response);
                        self.$uploadStatusContainer.empty();
                        self.updateUploadButton(false, false);
                        self.updateUploadFormUI();
                        self.$container.find(self.uploadCompleteLabelSelector).removeClass('hide');
                        self.allowClose = true;
                    },
                    error: function (response) {
                        response = JSON.parse(response.responseText);
                        self.$container.find(".hqm-error").removeClass('hide');
                        self.$container.find(".hqm-errors").html(_.template(self.errorsTemplate)({
                            errors: response.errors,
                        }));
                        self.$container.find(".hqm-begin").hide();
                        self.updateUploadButton(false, false);
                        self.allowClose = true;
                    },
                });
            });
        };

        return self;
    };

    return {
        get: get,
        uploader: uploader,
    };
});
