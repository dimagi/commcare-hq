function HQMediaUploadController(options) {
    var self = this;

    // These are necessary for having multiple upload controllers on the same page.
    self.container = options.container || '#hqmedia_uploader';
    self.marker = options.marker || 'media_';

    ///// YUI Uploader Specific Params
    self.confirmUploadModalSelector = options.confirmUploadModalSelector || "#hqm-upload-modal";
    self.swfURL = options.swfURL;
    self.fileFilters = options.fileFilters;
    self.isMultiFileUpload = options.isMultiFileUpload;

    // Essential Selectors
    self.selectFilesButtonContainer = self.container + " .hqm-select-files-container";
    self.selectFilesButton = self.container + " .hqm-select";

    self.uploadButtonSelector = self.container + " .hqm-upload";
    self.confirmUploadSelector = self.container + " .hqm-upload-confirm";

    self.processingFilesListSelector = self.container + " .hqm-upload-processing";
    self.uploadedFilesListSelector = self.container + " .hqm-uploaded-files";
    self.queueSelector = self.container + " .hqm-queue";
    self.uploadFormSelector = self.container + " .hqm-upload-form";

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
    self.pollInterval = 1000;
    self.currentPollAttempts = 0;
    self.maxPollAttempts = 30;

    self.processQueueTemplate = function (file) {
        /*
            This renders the template for the queued item display.
         */
        return _.template(self.queueTemplate, {
            unique_id: self.marker + file.get('id'),
            file_size: (file.get('size')/1048576).toFixed(3),
            file_name: file.get('name')
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

    self.cancelFileUpload = function (file) {
        /*
            What happens when you cancel or remove the file from queue.
         */
        if (self.isMultiFileUpload) {
            return function (event) {
                file.cancelUpload();
                var activeSelector = self.getActiveUploadSelectors(file.get('id'));
                self.removeFileFromUploaderUI(file);
                event.preventDefault();
            }
        } else {
            // single file upload
            return function (event) {
                // todo implement this
            }
        }
    };

    self.removeFileFromUI = function (file) {
        console.log("remove file from uploader ui");
        console.log(self.uploader.get('fileList'));
        var activeSelector = self.getActiveUploadSelectors(file.get('id'));
        $(activeSelector.selector).remove();
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
            base: '/static/hqmedia/yui/3.9.1/build/'
        }).use('uploader', function (Y) {
                Y.Uploader = Y.UploaderFlash;
                var buttonRegion = Y.one(self.selectFilesButton).get('region');
                console.log(Y.Uploader.TYPE);

                self.uploader = new Y.Uploader({
                    width: buttonRegion.width,
                    height: buttonRegion.height,
                    selectFilesButton: Y.one(self.selectFilesButton),
                    multipleFiles: self.isMultiFileUpload
                });

                if (Y.Uploader.TYPE == "html5") {
                    console.log("using HTML5 Uploader");
                }
                else if (Y.Uploader.TYPE == "flash") {
                    self.uploader.set("fileFilters", self.fileFilters);
                    self.uploader.set("swfURL", self.swfURL);
                }

                self.uploader.on("fileselect", self.fileSelect);
                self.uploader.render(self.selectFilesButtonContainer);
        });
//        YUI({
//            combine: false,
//            base: '/static/hqmedia/yui/'
//        }).use('uploader','uploader-flash', function (Y) {
//
//                if (Y.Uploader.TYPE != "none") {
//                    self.uploader = new Y.Uploader({
//                        selectFilesButton: self.selectFilesButton,
////                    boundingBox: self.boundingBox,
////                    swfURL: self.swfURL
//                    });
//
//                    if (Y.Uploader.TYPE == "html5") {
//                        console.log("using HTML5 Uploader");
////                    uploader.set("dragAndDropArea", "#divContainer");
//                    }
//                    else if (Y.Uploader.TYPE == "flash") {
//                        console.log("using Flash Uploader");
//                        self.uploader.set("fileFilters", self.fileFilters);
//                    }
//
//                    self.uploader.set("multipleFiles", self.isMultiFileUpload);
//                    self.uploader.set("simLimit", 2);
//                    self.uploader.render(self.boundingBox);
//
//                    self.uploader.on("fileselect", self.fileSelect);
//                    self.uploader.on("uploadprogress", self.uploadProgress);
//                    self.uploader.on("uploadcomplete", self.uploadComplete);
//                    self.uploader.on("uploadcompletedata", self.uploadCompleteData);
//                    self.uploader.on("uploaderror", self.uploadError);
//                }
//
//
//
//        });

        $(function () {
            self.resetUploader();
            $(self.confirmUploadSelector).click(self.startUpload);
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
        self.processingIdToFile = {};
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

    self.fileSelect = function (event) {
        /*
            After files have been selected by the select files function, do this.
         */
        console.log(event);
        console.log(self.uploader.get('fileList'));
        for (var f = 0; f < event.fileList.length; f++) {
            var queuedFile = event.fileList[f];
            var fileId = queuedFile.get('id');
            if (self.selectedFiles.indexOf(fileId) < 0) {
                self.selectedFiles.push(fileId);
                $(self.queueSelector).append(self.processQueueTemplate(queuedFile));
                var activeSelector = self.getActiveUploadSelectors(fileId);
                $(activeSelector.cancel).click(self.cancelFileUpload(queuedFile));
                if ($(activeSelector.remove)) {
                    $(activeSelector.remove).click(self.removeFileFromUploader(queuedFile));
                }
            }



//            if (event.fileList.hasOwnProperty(file_id) && !(file_id in self.selectedFiles)) {
//                var currentFile = event.fileList[file_id];
//                if (!self.isMultiFileUpload) {
//                    $(self.queueSelector).empty();
//                }
//                if (self.selectedFiles.indexOf(file_id) < 0) {
//                    $(self.queueSelector).append(self.processQueueTemplate(currentFile));
//                    self.selectedFiles.push(file_id);
//                    var activeSelector = self.getActiveUploadSelectors(file_id);
//
//                }
//            }
        }
//        self.toggleUploadButton();
//        self.resetUploadForm();
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
        self.removeFileFromUploaderUI(event.id);

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

    self.uploadError = function (event) {
        var file_id = event.id;
        var curUpload = self.getActiveUploadSelectors(file_id);
        $(curUpload.progressBarContainer).addClass('progress-danger');
        self.handleErrors(file_id, ['There is an issue communicating with the server at this time. The upload failed.']);
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
        self.currentPollAttempts = 0;
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
        return function (data, status) {
            self.currentPollAttempts += 1;
            if (self.currentPollAttempts > self.maxPollAttempts) {
                var file_id = self.processingIdToFile[processing_id];
                delete self.processingIdToFile[processing_id];
                var curUpload = self.getActiveUploadSelectors(file_id);
                self.stopProcessingFile(file_id);
                $(curUpload.progressBarContainer).addClass('progress-danger');
                self.handleErrors(file_id, ['There was an issue communicating with the server at this time. ' +
                    'The upload has failed.']);
            }
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
