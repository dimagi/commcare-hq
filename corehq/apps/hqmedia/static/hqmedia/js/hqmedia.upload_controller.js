function HQMediaUploadController(options) {
    var self = this;

    // These are necessary for having multiple upload controllers on the same page.
    self.container = options.container || '#hqmedia_uploader';
    self.marker = options.marker || 'media_';

    ///// YUI Uploader Specific Params
    self.boundingBox = options.boundingBox || (self.container + " .hqm-bounding-box");  // The element that's responsible for housing the swf that controls the upload process. This is the most important, functional part of this uploader.
    self.buttonSkin = options.buttonSkin;
    self.swfURL = options.swfURL;
    self.fileFilters = options.fileFilters;
    self.isMultiFileUpload = options.isMultiFileUpload;

    // Custom Selectors
    self.selectFilesSelector = options.selectFilesSelector || (self.container + " .hqm-select");
    self.uploadButtonSelector = options.uploadButtonSelector || (self.container + " .hqm-upload");
    self.beginUploadButtonSelector = options.beginUploadButtonSelector || (self.container + " .hqm-upload-begin");
    self.confirmUploadButtonSelector = options.confirmUploadButtonSelector || (self.container + " .hqm-upload-confirm");
    self.confirmUploadModalSelector = options.confirmUploadModalSelector || "#hqm-upload-modal";
    self.processingFilesListSelector = options.processingFilesListSelector || (self.container + " .hqm-upload-processing");
    self.uploadedFilesListSelector = options.uploadedFilesListSelector || (self.container + " .hqm-uploaded-files");
    self.queueSelector = options.queueSelector || (self.container + " .hqm-queue");
    self.uploadFormSelector = options.uploadFormSelector || (self.container + " .hqm-upload-form");

    // Text and templates
    self.queueTemplate = options.queueTemplate;
    self.detailsTemplate = options.detailsTemplate;
    self.statusTemplate = options.statusTemplate;
    self.errorsTemplate = options.errorsTemplate;

    // Stuff for processing the upload
    self.uploadParams = options.uploadParams || {};
    self.licensingParams = options.licensingParams || [];
    self.uploadURL = options.uploadURL;
    self.processingURL = options.processingURL;

    // Other
    self.uploadedFiles = [];
    self.processingIdToFile = {};
    self.pollInterval = 1000;

    self.processQueueTemplate = function (upload_info) {
        /*
            This renders the template for the queued item display.
         */
        return _.template(self.queueTemplate, {
            unique_id: self.marker + upload_info.id,
            file_size: (upload_info.size/1048576).toFixed(3),
            file_name: upload_info.name
        });
    };

    self.processDetailsTemplate = function (images, audio, unknowns) {
        return _.template(self.detailsTemplate, {
            images: images,
            audio: audio,
            unknowns: unknowns
        });
    };

    self.processStatusTemplate = function (images, audio) {
        var numMatches = images.length + audio.length;
        return _.template(self.statusTemplate, {
            num: numMatches
        });
    };

    self.processErrorsTemplate = function (errors) {
        return _.template(self.errorsTemplate, {
            errors: errors
        });
    };

    self.cancelFileUpload = function (upload_info) {
        /*
            What happens when you cancel or remove the file from queue.
         */
        var file_id = upload_info.id;
        if (self.isMultiFileUpload) {
            return function (event) {
                self.uploader.cancel(file_id);
                self.removeFileFromUploader(file_id);
                var activeSelector = self.getActiveUploadSelectors(file_id);
                $(activeSelector.selector).remove();
                event.preventDefault();
            }
        } else {
            // single file upload
            return function (event) {
                // todo implement this
            }
        }
    };

    self.getActiveUploadSelectors = function (upload_id) {
        /*
            All the different active parts of the queued item template that the upload controller cares about.
         */
        var selector = '#' + self.marker + upload_id;
        return {
            selector: selector,
            progressBarContainer: selector + ' .progress',
            progressBar: selector + ' .progress .bar',
            cancel: selector + ' .hqm-cancel',
            remove: selector + ' .hqm-remove',
            beginNotice: selector + ' .hqm-begin',
            processingQueuedNotice: selector + ' .hqm-processing-queued',
            processingNotice: selector + ' .hqm-processing',
            completeNotice: selector + ' .hqm-upload-completed',
            errorNotice: selector + ' .hqm-error',
            status: selector + ' .hqm-status',
            details: selector + ' .hqm-details'
        }
    };

    self.init = function () {
        /*
            Initialize the uploader.

            Here we use YUI for the uploader. Flash is required.
            We tried non Flash at some point and gave up after a myriad of issues.
         */
        YUI({
            combine: false,
            base: '/static/hqmedia/yui/'
        }).use("uploader", function (Y) {
            Y.on("domready", function () {
                $(self.boundingBox).width($(self.selectFilesSelector).outerWidth()).height($(self.selectFilesSelector).outerHeight());

                self.uploader = new Y.Uploader({
                    buttonSkin: self.buttonSkin,
                    boundingBox: self.boundingBox,
                    swfURL: self.swfURL
                });

                self.uploader.on("uploaderReady", self.uploaderReady);
                self.uploader.on("fileselect", self.fileSelect);
                self.uploader.on("uploadprogress", self.uploadProgress);
                self.uploader.on("uploadcomplete", self.uploadComplete);
                self.uploader.on("uploadcompletedata", self.uploadCompleteData);
            });
        });

        $(function () {
            self.resetUploader();
            $(self.confirmUploadButtonSelector).click(self.startUpload);
            $(self.uploadFormSelector).find('.hqm-share-media').change(function () {
                var $sharingOptions = $(self.uploadFormSelector).find('.hqm-sharing');
                ($(this).prop('checked')) ? $sharingOptions.removeClass('hide') : $sharingOptions.addClass('hide');
            });
        });
    };

    self.resetUploader = function () {
        /*
            Start over.
         */
        self.selectedFiles = [];
        self.uploadedFiles = [];
        self.toggleUploadButton();
        self.resetUploadForm();
    };

    self.resetUploadForm = function () {
        var $uploadForm = $(self.uploadFormSelector);
        $uploadForm.find('.hqm-share-media').removeAttr('checked');
        $uploadForm.find('.hqm-sharing').addClass('hide');
        $uploadForm.find('[name="license"]').val('cc');
        $uploadForm.find('[name="author"]').val('');
        $uploadForm.find('[name="attribution-notes"]').val('');
    };

    self.getLicensingParams = function () {
        var $form = $(self.uploadFormSelector),
            params = {};
        for (var i = 0; i < self.licensingParams.length; i++) {
            var param_name = self.licensingParams[i];
            var param_val = $form.find('[name="' + param_name + '"]').val();
            if (param_val.length > 0) params[param_name] = param_val;
        }
        return params;
    };

    self.uploaderReady = function (event) {
        /*
            When the uploader is ready, set these things.
         */
        self.uploader.set("multiFiles", self.isMultiFileUpload);
        self.uploader.set("simLimit", 3);
        self.uploader.set("log", true);
        self.uploader.set("fileFilters", self.fileFilters);
    };

    self.fileSelect = function (event) {
        /*
            After files have been selected by the select files function, do this.
         */
        for (var file_id in event.fileList) {
            if (event.fileList.hasOwnProperty(file_id) && !(file_id in self.selectedFiles)) {
                var currentFile = event.fileList[file_id];
                if (!self.isMultiFileUpload) {
                    $(self.queueSelector).empty();
                }
                if (self.selectedFiles.indexOf(file_id) < 0) {
                    $(self.queueSelector).append(self.processQueueTemplate(currentFile));
                    self.selectedFiles.push(file_id);
                    var activeSelector = self.getActiveUploadSelectors(file_id);
                    $(activeSelector.cancel).click(self.cancelFileUpload(currentFile));
                    if (activeSelector.remove) {
                        $(activeSelector.remove).click(self.cancelFileUpload(currentFile));
                    }
                }
            }
        }
        self.toggleUploadButton();
        self.resetUploadForm();
    };

    self.startUpload = function (event) {
        $(self.confirmUploadModalSelector).modal('hide');
        var currentParams = _.clone(self.uploadParams);
        if ($(self.uploadFormSelector).find('[name="shared"]').prop('checked')) {
            $.extend(currentParams, self.getLicensingParams());
        }
        for (var key in self.uploadParams) {
            if (self.uploadParams.hasOwnProperty(key)
                && $(self.uploadFormSelector).find('[name="'+key+'"]').prop('checked')) {
                currentParams[key] = true;
            }
        }
        self.uploader.uploadAll(self.uploadURL, "POST", currentParams);
        self.activateQueue();
        event.preventDefault();
    };

    self.uploadProgress = function (event) {
        var currentProgress = Math.round(100 * event.bytesLoaded / event.bytesTotal),
            curUpload = self.getActiveUploadSelectors(event.id);
        $(curUpload.progressBar).attr('style', 'width: ' + Math.min(currentProgress, 100) + '%;');
    };

    self.uploadComplete = function (event) {
        var curUpload = self.getActiveUploadSelectors(event.id);
        $(curUpload.progressBarContainer).removeClass('active');
        $(curUpload.cancel).addClass('hide');
        self.removeFileFromUploader(event.id);

        if (self.isMultiFileUpload) {
            var $queuedItem = $(curUpload.selector);
            $queuedItem.remove();
            $queuedItem.insertAfter($(self.processingFilesListSelector).find('.hqm-list-notice'));
        }
    };

    self.uploadCompleteData = function (event) {
        var response = $.parseJSON(event.data);
        self.beginProcessing(event, response);
    };

    self.toggleUploadButton = function () {
        var $uploadButton = $(self.uploadButtonSelector);
        if (self.isMultiFileUpload) {
            (self.selectedFiles.length > 0) ? $uploadButton.addClass('btn-success').removeClass('disabled') : $uploadButton.addClass('disabled').removeClass('btn-success');
        }
    };

    self.activateQueue = function () {
        for (var i=0; i < self.selectedFiles.length; i++) {
            var file_id = self.selectedFiles[i];
            var currentSelector = self.getActiveUploadSelectors(file_id);
            $(currentSelector.beginNotice).addClass('hide');
            $(currentSelector.remove).addClass('hide');
            $(currentSelector.cancel).removeClass('hide');
        }
    };

    self.removeFileFromUploader = function (file_id) {
        self.uploader.removeFile(file_id);
        self.selectedFiles = _.without(self.selectedFiles, file_id);
        self.toggleUploadButton();
    };

    self.beginProcessing = function(event, response) {
        var processing_id = response.processing_id;
        self.processingIdToFile[response.processing_id] = event.id;
        var curUpload = self.getActiveUploadSelectors(event.id);
        $(curUpload.progressBar).addClass('hide').attr('style', 'width: 0%;'); // reset progress bar for processing
        $(curUpload.progressBarContainer).addClass('progress-warning active');
        $(curUpload.processingQueuedNotice).removeClass('hide');
        self.pollProcessingQueue(processing_id)();
    };

    self.pollProcessingQueue = function (processing_id) {
        return function _poll () {
            setTimeout(function () {
                if (processing_id in self.processingIdToFile) {
                    $.ajax({
                        url: self.processingURL,
                        dataType: 'json',
                        data: {
                            processing_id: processing_id
                        },
                        type: 'POST',
                        success: self.handleProcessingQueue,
                        error: self.handleProcessingQueueError(processing_id),
                        complete: _poll,
                        timeout: self.pollInterval
                    });
                }
            }, self.pollInterval);
        }
    };

    self.handleProcessingQueue = function (data) {
        var file_id = self.processingIdToFile[data.processing_id];
        var curUpload = self.getActiveUploadSelectors(file_id);
        if (data.in_celery) {
            $(curUpload.processingQueuedNotice).addClass('hide');
            $(curUpload.processingNotice).removeClass('hide');
            $(curUpload.progressBar).removeClass('hide').attr('style', 'width: ' + data.progress + '%;');
            if (data.total_files) {
                var $file_status = $(curUpload.processingNotice).find('.label');
                $file_status.find('.denominator').text(data.total_files);
                $file_status.find('.numerator').text(data.processed_files || 0);
                $file_status.removeClass('hide');
            }
        }
        if (data.complete) {
            self.handleProcessingQueueComplete(data);
        }
    };

    self.handleProcessingQueueComplete = function (data) {
        var file_id = self.processingIdToFile[data.processing_id];
        delete self.processingIdToFile[data.processing_id];
        var curUpload = self.getActiveUploadSelectors(file_id);
        self.stopProcessingFile(file_id);
        $(curUpload.progressBarContainer).addClass('progress-success');

        self.showMatches(file_id, data);
        self.handleErrors(file_id, data.errors);
    };

    self.stopProcessingFile = function (file_id) {
        var curUpload = self.getActiveUploadSelectors(file_id);
        if (self.isMultiFileUpload) {
            var $processingItem = $(curUpload.selector);
            $processingItem.remove();
            $processingItem.insertAfter($(self.uploadedFilesListSelector).find('.hqm-list-notice'));
        }

        $(curUpload.processingNotice).addClass('hide');
        $(curUpload.completeNotice).removeClass('hide');
        $(curUpload.progressBar).attr('style', 'width: 100%;');
        $(curUpload.progressBarContainer).removeClass('active progress-warning');
    };

    self.handleProcessingQueueError = function (processing_id) {
        return function (data) {
            var file_id = self.processingIdToFile[processing_id];
            delete self.processingIdToFile[processing_id];
            var curUpload = self.getActiveUploadSelectors(file_id);
            self.stopProcessingFile(file_id);
            $(curUpload.progressBarContainer).addClass('progress-danger');
            self.handleErrors(file_id, ['There was an issue communicating with the server. The upload failed.']);
        }
    };

    self.showMatches = function (file_id, data) {
        var curUpload = self.getActiveUploadSelectors(file_id);
        if (data.type === 'zip' && data.matched_files) {
            var images = data.matched_files.CommCareImage,
                audio = data.matched_files.CommCareAudio,
                unknowns = data.unmatched_files;
            $(curUpload.status).append(self.processStatusTemplate(images, audio));

            $(curUpload.details).html(self.processDetailsTemplate(images, audio, unknowns));
            $(curUpload.details).find('.match-info').popover({
                html: true,
                title: 'Click to open in new tab.',
                trigger: 'hover',
                placement: 'bottom'
            });
        }
    };

    self.handleErrors = function (file_id, errors) {
        var selector = self.getActiveUploadSelectors(file_id);
        (errors.length > 0) ? $(selector.errorNotice).removeClass('hide') : $(selector.errorNotice).addClass('hide');
        $(selector.status).append(self.processErrorsTemplate(errors));
    };

}
