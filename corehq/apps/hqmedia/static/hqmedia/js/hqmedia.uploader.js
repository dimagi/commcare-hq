function HQMediaUploader(options) {
    var self = this;
    self.uploadElem = (options.uploadElem) ? options.uploadElem : '#hqmedia_upload';
    self.fileFilters = (options.fileFilters) ? options.fileFilters : new Array({description:"Images", extensions:"*.jpg;*.png;*.gif"});
    self.uploadURL = (options.uploadURL) ? options.uploadURL : "";
    self.singleFileUpload = (options.singleFileUpload) ? options.singleFileUpload : false;
    self.onSuccess = options.onSuccess;
    self.buttonImage = (options.buttonImage) ? options.buttonImage : "";
    self.uploadParams = (options.uploadParams) ? options.uploadParams : {};
    self.modalClass = (options.modalClass) ? options.modalClass : "";
    self.mediaType = (options.mediaType) ? options.mediaType : "hqmedia_";
    self.swfLocation = options.swfLocation;

    self.render = function() {
        YUI({combine: false, base: '/static/hqmedia/yui/'}).use("uploader", function(Y) {
            var upEl = this;
            var uploader = undefined,
                selectedFiles = {},
                currentNumFiles = 0;
            Y.on("domready", init);

            function init () {

                var params,
                    overlaySelector = self.uploadElem+" .hqm-overlay";
                if (self.buttonImage) {
                    params = {
                        buttonSkin: self.buttonImage,
                        boundingBox: overlaySelector,
                        swfURL: self.swfLocation};
                }else {
                    var overlayRegion = Y.one(self.uploadElem+" .hqm-select").get('region');
                    Y.one(overlaySelector).set("offsetWidth", overlayRegion.width);
                    Y.one(overlaySelector).set("offsetHeight", overlayRegion.height);
                    params = {boundingBox: overlaySelector,
                                swfURL: self.swfLocation};
                }

                uploader = new Y.Uploader(params);

                uploader.on("uploaderReady", setupUploader);
                uploader.on("fileselect", fileSelect);
                uploader.on("uploadprogress", updateProgress);
                uploader.on("uploadcomplete", uploadComplete);
                uploader.on("uploadcompletedata", uploadCompleteData);

                Y.one(self.uploadElem+" .hqm-upload-button").on("click", uploadFile);

                if (self.singleFileUpload) {
                    $(self.uploadElem+" .hqm-cancel").click(function() {
                        uploader.cancel();
                        uploader.clearFileList();
                        showCancelButton(false);
                        showUploadButton(false);
                        showSelectContainer(true);
                        $(self.uploadElem+' .hqm-upload-list').text('');
                        $(self.uploadElem+' .hqm-file_selected_only').addClass('hide');
                    });
                }

                if (self.modalClass) {
                    $(self.modalClass).on('hidden', function () {
                        resetUploader();
                    });
                }

            }

            function setupUploader(event) {
                uploader.set("multiFiles", !self.singleFileUpload);
                uploader.set("simLimit", 3);
                uploader.set("log", true);
                uploader.set("fileFilters", self.fileFilters);
            }

            function fileSelect(event) {
                // enable the upload button with the file list populated
                showUploadButton(true);

                var fileData = event.fileList;
                for (var key in fileData) {
                    var output;
                    if (self.singleFileUpload) {
                        output = '<div id="'+self.mediaType+fileData[key].id+'">\
                            <span class="help-inline" style="line-height:28px;">'+fileData[key].name+' ['+(fileData[key].size/1048576).toFixed(3)+' MB]</span>\
                            <a href="#" class="hqm-change btn btn-small">\
                                <i class="icon icon-remove"></i> Change File\
                            </a>\
                            <div class="progress progress-striped active" style="margin-top: 5px;">\
                                <div class="bar" style="width: 0%;"></div>\
                            </div>\
                        </div>';
                        $(self.uploadElem+' .hqm-upload-list').html(output);

                        $(self.uploadElem+' .hqm-file_selected_only').removeClass('hide');
                        $(self.uploadElem+" .control-group").removeClass('success').removeClass('error');
                        $(self.uploadElem+' .hqm-change').click(function () {
                            uploader.cancel();
                            uploader.clearFileList();
                            $(self.uploadElem+' .hqm-upload-list').text('');
                            showSelectContainer(true);
                            showUploadButton(false);
                            showCancelButton(false);
                            $(self.uploadElem+' .hqm-file_selected_only').addClass('hide');
                            return false;
                        });
                        showSelectContainer(false);

                    } else if(!selectedFiles[fileData[key].id]) {
                        if(currentNumFiles < 1)
                            $(self.uploadElem+" .hqm-empty_queue-notice").addClass('hide');
                        currentNumFiles += 1;

                        output = '<tr id="'+self.mediaType+fileData[key].id+'">\
                            <td>'+fileData[key].name+'</td>\
                            <td>'+(fileData[key].size/1048576).toFixed(3)+' MB</td>\
                            <td class="upload_progress">\
                                <div class="progress progress-striped active" style="margin-bottom: 5px;">\
                                    <div class="bar" style="width: 0%;"></div>\
                                </div>\
                                <a href="#" class="btn btn-danger btn-mini pull-right hqm-cancel">\
                                    <i class="icon icon-white icon-remove"></i> Cancel\
                                </a>\
                            </td>\
                            <td class="match_status"></td>\
                            <td class="details"></td>\
                        </tr>';
                        // add the file info to the queue list
                        $(self.uploadElem+' .hqm-upload-list').find("tbody.queue").append(output);

                        $('#'+self.mediaType+fileData[key].id+' .hqm-cancel').click(function () {
                            var $parentElement = $(this).parent().parent();
                            var fileId = $parentElement.attr('id').replace(self.mediaType, '');
                            uploader.cancel(fileId);
                            uploader.removeFile(fileId);
                            currentNumFiles -= 1;
                            $parentElement.remove();
                            if(currentNumFiles < 1) {
                                $(self.uploadElem+" .hqm-empty_queue-notice").removeClass('hide');
                                showUploadButton(false);
                            }
                            return false;
                        });
                        selectedFiles[fileData[key].id] = true;
                    }

                }
            }

            function updateProgress(event) {
                var progress_total = Math.round(100 * event.bytesLoaded / event.bytesTotal),
                    pb_parentSel = '#'+self.mediaType+event.id+' .progress';
                $(pb_parentSel+' .bar').attr('style', 'width: '+progress_total+'%;');

                if (progress_total >= 100) {
                    if (self.singleFileUpload) {
                        showCancelButton(false);
                    } else {
                        var next_el = $(pb_parentSel).next();
                        if (next_el && next_el.hasClass('hqm-cancel') || next_el.hasClass('label'))
                            next_el.remove();
                    }
                    var $processing = $('<div class="label label-info pull-right" />');
                    $processing.text('Processing, please wait.');
                    $(pb_parentSel).addClass('progress-warning').after($processing);
                }
            }

            function uploadComplete(event) {
                // remove the successfully uploaded file from the file list
                showSelectContainer(true);
                showCancelButton(false);

                var pb_parentSel = '#'+self.mediaType+event.id+' .progress';
                $(pb_parentSel+' .bar').attr('style', 'width: 100%;');
                $(pb_parentSel).removeClass('active progress-warning').addClass('progress-success');

                var next_el = $(pb_parentSel).next();
                if (next_el && (next_el.hasClass('hqm-cancel') || next_el.hasClass('label')))
                    next_el.remove();

                if (self.singleFileUpload) {
                    $(self.uploadElem+" .control-group").addClass('success');
                    $(self.uploadElem+" .control-group .controls").append($('<p class="help-block" />').text('Upload successful.'));
                    uploader.clearFileList();
                } else {
                    uploader.removeFile(event.id);
                    currentNumFiles -= 1;
                    if(currentNumFiles < 1)
                        $(self.uploadElem+" .hqm-empty_queue-notice").removeClass('hide');

                    var $uploadFileElem = $('#'+self.mediaType+event.id);
                    $uploadFileElem.remove();
                    $(self.uploadElem+' .hqm-upload-list').find("tbody.done").prepend($uploadFileElem);

                    $(self.uploadElem+" .hqm-uploaded-notice").removeClass("hide");
                }
            }

            function resetUploader() {
                $(self.uploadElem+' .hqm-upload-list').text('');
                showUploadButton(false);
                showSelectContainer(true);
                showCancelButton(false);
                uploader.cancel();
                uploader.clearFileList();
                if (self.singleFileUpload)
                    $(self.uploadElem+' .hqm-file_selected_only').addClass('hide');
            }

            function uploadFile(event) {
                if ($(self.uploadElem+' .hqm-share-media').attr('checked'))
                    self.uploadParams['shared'] = 't';
                self.uploadParams['tags'] = $(self.uploadElem+' .hqm-media-tags').val();
                showUploadButton(false);
                showCancelButton(true);
                if (self.singleFileUpload)
                    $(self.uploadElem+' .hqm-change').remove();
                uploader.uploadAll(self.uploadURL, "POST", self.uploadParams);
            }

            function uploadCompleteData(event) {
                var resp = $.parseJSON(event.data);
                if(self.onSuccess)
                    self.onSuccess(event, resp);

                var $currentMedia = $('#hqmedia_'+event.id);
                if (!_.isEmpty(resp.errors)) {
                    $currentMedia.find('.progress').removeClass('progress-success').addClass('progress-danger');
                    if (self.singleFileUpload) {
                        $(self.uploadElem+" .control-group").addClass('error').removeClass('success');
                        $(self.uploadElem+" .control-group .controls .help-block").text('Error uploading.');
                        for (var e in resp.errors) {
                            $(self.uploadElem+" .control-group .controls").append($('<p class="label label-important" style="margin-top:5px;" />').text("ERROR: "+resp.errors[e]));
                        }
                    } else
                        for (var e in resp.errors) {
                            $currentMedia.find('.match_status').append($('<div class="label label-important" style="margin-top:5px;" />').text("ERROR: "+resp.errors[e]));
                        }
                }
            }

            function showSelectContainer(toggle_on) {
                var $selectContainer = $(self.uploadElem+" .hqm-select-container");
                if ($selectContainer)
                    (toggle_on) ? $selectContainer.attr('style', '') : $selectContainer.attr('style', 'visibility: hidden;');
            }

            function showUploadButton(toggle_on) {
                var $uploadButton = $(self.uploadElem+" .hqm-upload-button").css('float', 'none').css('text-align', 'left');
                $uploadButton.find('input[type=text]').css('float', 'none').css('text-align', 'left');
                if (self.singleFileUpload)
                    (toggle_on) ? $uploadButton.removeClass('hide') : $uploadButton.addClass('hide');
                else {
                    (toggle_on) ? $uploadButton.addClass('btn-success').removeClass('disabled') : $uploadButton.addClass('disabled').removeClass('btn-success');
                }
                if (!toggle_on)
                    $(self.uploadElem+" .hqm-media-tags").val('');
            }

            function showCancelButton(toggle_on) {
                if (self.singleFileUpload) {
                    var $cancelButton = $(self.uploadElem+" .hqm-cancel");
                    (toggle_on) ? $cancelButton.removeClass('hide') : $cancelButton.addClass('hide');
                }
            }

        });
    };
}