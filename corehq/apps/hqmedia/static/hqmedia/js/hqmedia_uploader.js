function HQMediaUploader(options) {
    var self = this;
    var fileFilters = options.fileFilters,
        uploadURL = options.uploadURL,
        onSuccess = options.onSuccess;

    self.render = function() {
        YUI().use("uploader", function(Y) {
            var uploader;
            Y.on("domready", init);

            function init () {
                var overlayRegion = Y.one("#hqmedia-select-button").get('region');
                Y.log(overlayRegion);
                Y.one("#hqmedia-uploader-overlay").set("offsetWidth", overlayRegion.width);
                Y.one("#hqmedia-uploader-overlay").set("offsetHeight", overlayRegion.height);

                uploader = new Y.Uploader({boundingBox:"#hqmedia-uploader-overlay"});

                uploader.on("uploaderReady", setupUploader);
                uploader.on("fileselect", fileSelect);
                uploader.on("uploadprogress", updateProgress);
                uploader.on("uploadcomplete", uploadComplete);
                uploader.on("uploadcompletedata", uploadCompleteData);

                Y.one("#hqmedia-upload-button").on("click", uploadFile);
            }

            function setupUploader(event) {
                uploader.set("multiFiles", true);
                uploader.set("simLimit", 3);
                uploader.set("log", true);

                uploader.set("fileFilters", fileFilters);
            }

            function fileSelect(event) {
                Y.log("File was selected, parsing...");
                var fileData = event.fileList;
                for (var key in fileData) {
                    var output = '<tr id="hqmedia_'+fileData[key].id+'">\
                        <td>'+fileData[key].name+'</td>\
                        <td>'+fileData[key].size+' bytes</td>\
                        <td class="upload_progress"><div class="progress progress-striped active" ><div class="bar" style="width: 0%;"></div></td>\
                        <td class="match_status"></td>\
                        <td class="details"></td>\
                    </tr>';
                    Y.one("#hqmedia-queue tbody").append(output);
                }
            }

            function updateProgress(event) {
                $('#hqmedia_'+event.id+' .upload_progress .progress .bar').attr('style', 'width: '+Math.round(100 * event.bytesLoaded / event.bytesTotal)+'%;');
            }

            function uploadComplete(event) {
                console.log('upload complete');
                console.log(event);
                $('#hqmedia_'+event.id+' .upload_progress .progress .bar').attr('style', 'width: 100%;');
                $('#hqmedia_'+event.id+' .upload_progress .progress').removeClass('active');
            }

            function uploadFile(event) {
                console.log("upload file");
                console.log(event);
                uploader.uploadAll(uploadURL);
            }

            function uploadCompleteData (event) {
                if (onSuccess) {
                    onSuccess(event, $.parseJSON(event.data))
                }
            }
        });
    };
}