hqDefine("hqmedia/js/uploaders", [
    "jquery",
    "underscore",
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    _,
    assertProperties,
    initialPageData
) {
    const uploader = function (slug, options) {
        assertProperties.assertRequired(options, [
            'uploadURL', 'uploadParams',
            'queueTemplate', 'errorsTemplate', 'existingFileTemplate',
        ]);

        let self = {};
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

            if (self.currentReference && self.currentReference.getUrl() && self.currentReference.isMediaMatched()) {
                self.$existingFile.removeClass('hide');
                self.$existingFile.find('.hqm-existing-controls').html(_.template(options.existingFileTemplate)({
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

        self.$container.on('show.bs.modal', function () {
            self.updateUploadFormUI();
        });

        // Don't allow user to close modal while server is processing upload
        self.$container.on('hide.bs.modal', function (event) {
            if (!self.allowClose) {
                event.preventDefault();
            }
        });

        self.$fileInputTrigger.click(function () {
            self.$fileInput.click();
        });

        self.$fileInput.change(function () {
            const MEGABYTE = 1048576;

            if (self.$fileInput.get(0).files.length) {
                const file = self.$fileInput.get(0).files[0];
                self.$uploadStatusContainer.html(_.template(options.queueTemplate)({
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

            const file = self.$fileInput.get(0).files[0],
                data = new FormData();
            data.append("Filedata", file);

            if (self.uploadParams.path) {
                const newExtension = '.' + file.name.split('.').pop().toLowerCase();
                self.uploadParams.path = self.uploadParams.path.replace(/(\.[^/.]+)?$/, newExtension);
            }
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
                    $('[data-hqmediapath^="' + self.currentReference.path.replace(/\.\w+$/, ".") + '"]').trigger('mediaUploadComplete', response);
                    self.$uploadStatusContainer.empty();
                    self.updateUploadButton(false, false);
                    self.updateUploadFormUI();
                    self.$container.find(self.uploadCompleteLabelSelector).removeClass('hide');
                    self.allowClose = true;
                },
                error: function (response) {
                    response = JSON.parse(response.responseText);
                    self.$container.find(".hqm-error").removeClass('hide');
                    self.$container.find(".hqm-errors").html(_.template(options.errorsTemplate)({
                        errors: response.errors,
                    }));
                    self.$container.find(".hqm-begin").hide();
                    self.updateUploadButton(false, false);
                    self.allowClose = true;
                },
            });
        });

        return self;
    };

    let allUploaders = {};
    const uploaderPreset = function (slug) {
        if (!allUploaders[slug]) {
            const options = _.find(initialPageData.get("uploaders"), function (data) { return data.slug === slug; });
            if (options) {
                allUploaders[slug] = uploader(options.slug, options.options);
            }
        }
        return allUploaders[slug];
    };

    return {
        uploader: uploader,
        uploaderPreset: uploaderPreset,
    };
});
