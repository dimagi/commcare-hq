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
    self.emptyNoticeSelector = options.emptyNoticeSelector || (self.container + " .hqm-empty");
    self.uploadedNoticeSelector = options.uploadedNoticeSelector || (self.container + " .hqm-uploaded-notice");
    self.uploadedFilesListSelector = options.uploadedFilesListSelector || (self.container + " .hqm-uploaded-files");
    self.queueSelector = options.queueSelector || (self.container + " .hqm-queue");
    self.uploadFormSelector = options.uploadFormSelector || (self.container + " .hqm-upload-form");

    // Text and templates
    self.queueTemplate = options.queueTemplate;
    self.noMatchFoundTemplate = options.noMatchFoundTemplate;
    self.detailsTemplate = options.detailsTemplate;
    self.matchesFoundTemplate = options.matchesFoundTemplate;

    // Stuff for processing the upload
    self.uploadParams = options.uploadParams || {};
    self.uploadFormParams = options.uploadFormParams || [];
    self.uploadURL = options.uploadURL;

    // Other
    self.uploadedFiles = [];

    self.processQueueTemplate = options.processQueueTemplate || function (upload_info) {
        /*
            This renders the template for the queued item display.
         */
        return _.template(self.queueTemplate, {
            unique_id: self.marker + upload_info.id,
            file_size: (upload_info.size/1048576).toFixed(3),
            file_name: upload_info.name
        });
    };

    self.processDetailsTemplate = options.processDetailsTemplate || function (response) {
        return _.template(self.detailsTemplate, {
            images: response.images,
            audio: response.audio,
            unknowns: response.unknown
        });
    };

    self.processMatchesTemplate = options.processMatchesTemplate || function (response) {
        var numMatches = _.keys(response.images).length + _.keys(response.audio).length;
        return _.template(self.matchesFoundTemplate, {
            num: numMatches
        });
    };

    self.cancelFileUploadFn = options.cancelFileUpload || function (upload_info) {
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

    self.handleErrorsFn = options.handleErrorsFn || function (file_id, errors) {
        var selector = self.getActiveUploadSelectors(file_id);
        $(selector.progressBarContainer).removeClass('progress-success').addClass('progress-danger');
        $(selector.completeNotice).addClass('hide');
        $(selector.errorNotice).removeClass('hide');
        for (var e = 0; e < errors.length; e++) {
            var error = errors[e];
            var $errorMsg = $('<p class="label label-important" style="margin-top: 5px;" />').text('ERROR: ' + error);
            $(selector.status).append($errorMsg);
        }
    };

    self.getActiveUploadSelectors = options.getActiveUploadSelectors || function (upload_id) {
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

    self.getPramsFromForm = function () {
        var $form = $(self.uploadFormSelector),
            params = {};
        for (var i = 0; i < self.uploadFormParams.length; i++) {
            var param_name = self.uploadFormParams[i];
            var param_val = $form.find('[name=' + param_name + ']').val();
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
                    $(activeSelector.cancel).click(self.cancelFileUploadFn(currentFile));
                    if (activeSelector.remove) {
                        $(activeSelector.remove).click(self.cancelFileUploadFn(currentFile));
                    }
                }
                self.toggleEmptyNotice();
            }
        }
        self.toggleUploadButton();
        self.resetUploadForm();
    };

    self.startUpload = function (event) {
        $(self.confirmUploadModalSelector).modal('hide');
        var currentParams = _.clone(self.uploadParams);
        if ($(self.uploadFormSelector).find('[name="shared"]').prop('checked')) {
            $.extend(currentParams, self.getPramsFromForm());
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
        $(curUpload.progressBar).attr('style', 'width: ' + currentProgress + '%;');
        if (currentProgress >= 100) {
            $(curUpload.cancel).addClass('hide');
            // todo, get updates from memcached as to how the processing is going server-side
            $(curUpload.processingNotice).removeClass('hide');
            $(curUpload.progressBarContainer).addClass('progress-warning');
        }
    };

    self.uploadComplete = function (event) {
        var curUpload = self.getActiveUploadSelectors(event.id);
        $(curUpload.progressBar).attr('style', 'width: 100%;'); // Double check that progress bar is at 100%
        $(curUpload.progressBarContainer).removeClass('active progress-warning').addClass('progress-success');
        $(curUpload.cancel).addClass('hide');
        $(curUpload.processingNotice).addClass('hide');
        $(curUpload.completeNotice).removeClass('hide');

        self.removeFileFromUploader(event.id);
        self.uploadedFiles.push(event.id);
        self.toggleUploadedFilesNotice();

        if (self.isMultiFileUpload) {
            var $queuedItem = $(curUpload.selector);
            $queuedItem.remove();
            $(self.uploadedFilesListSelector).prepend($queuedItem);
        }
    };

    self.uploadCompleteData = function (event) {
        var response = $.parseJSON(event.data);
        if (self.onSuccess) self.onSuccess(event, response);
        if (!_.isEmpty(response.errors)) {
            self.handleErrorsFn(event.id, response.errors);
        }
    };

    self.toggleUploadButton = function () {
        var $uploadButton = $(self.uploadButtonSelector);
        if (self.isMultiFileUpload) {
            (self.selectedFiles.length > 0) ? $uploadButton.addClass('btn-success').removeClass('disabled') : $uploadButton.addClass('disabled').removeClass('btn-success');
        }
    };

    self.toggleEmptyNotice = function () {
        var $emptyNotice = $(self.emptyNoticeSelector);
        if ($emptyNotice) {
            (self.selectedFiles.length < 1) ? $emptyNotice.removeClass('hide') : $emptyNotice.addClass('hide');
        }
    };

    self.toggleUploadedFilesNotice = function () {
        var $uploadedNotice = $(self.uploadedNoticeSelector);
        if ($uploadedNotice) {
            (self.uploadedFiles.length > 0) ? $uploadedNotice.removeClass('hide') : $uploadedNotice.addClass('hide');
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
        self.toggleEmptyNotice();
        self.toggleUploadButton();
    };

    self.onSuccess = options.onSuccess || function (event, response) {
        var curUpload = self.getActiveUploadSelectors(event.id);
        if (response.zip) {
            if (_.isEmpty(response.images) && _.isEmpty(response.audio)) {
                $(curUpload.status).html(self.noMatchFoundTemplate);
            } else {
                $(curUpload.status).html(self.processMatchesTemplate(response));
            }
            $(curUpload.details).html(self.processDetailsTemplate(response));
            $(curUpload.details).find('.match-info').popover({
                html: true,
                title: 'Click to open in new tab.',
                trigger: 'hover',
                placement: 'bottom'
            })
        }
    };

}
