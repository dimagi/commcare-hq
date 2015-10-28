$(function(){
    "use strict";

    window.AsyncDownloader = function($el, download_url){
        var self = this;
        self.POLL_FREQUENCY = 1500; //ms
        self.ERROR_MESSAGE = "Sorry, something went wrong with the download. " +
                             "If you see this repeatedly please report an issue.";
        self.download_url = download_url;

        self.$el = $el;
        self.el_id = $el.attr("id");
        self.$download_progress = self.$el.find("#" + self.el_id + "-download-progress");
        self.$downloading = self.$el.find("#" + self.el_id + "-downloading");

        self.download_in_progress = false;
        self.download_poll_url = null;
        self.download_poll_id = null;

        self.init = function(){
            self.download_in_progress = false;
            self.download_poll_url = null;
            self.download_poll_id = null;
            self.$download_progress.addClass("hide");
            self.$downloading.removeClass("hide");
        };

        self.pollDownloadStatus = function(){
            if (self.download_in_progress) {
                $.ajax({
                    url: self.download_poll_url,
                    success: function (resp) {
                        self.updateProgress(resp);
                        if (!self.isDone(resp)) {
                            setTimeout(self.pollDownloadStatus, self.POLL_FREQUENCY);
                        }
                    },
                    error: function (resp) {
                        self.downloadError(resp.responseText);
                    }
                });
            }
        };

        self.updateProgress = function (progress_response) {
            if (progress_response.trim().length) {
                self.$downloading.addClass("hide");
                self.$download_progress.html(progress_response).removeClass("hide");
            }
        };

        self.isDone = function (progress_response) {
            var ready_id = 'ready_' + self.download_poll_id,
                error_id = 'error_' + self.download_poll_id;
            return !!progress_response &&
                !!progress_response.trim().length &&
                !!_.find([ready_id, error_id], function(el_id) {
                    return progress_response.indexOf(el_id) > 0;
                });
        };

        self.generateDownload = function(){
            // prevent multiple calls
            if (!self.download_in_progress) {
                self.download_in_progress = true;
                $.ajax({
                    url: self.download_url,
                    type: "GET",
                    dataType: "json",
                    success: function (data) {
                        self.download_poll_url = data.download_url;
                        self.download_poll_id = data.download_id;
                        self.pollDownloadStatus();
                    },
                    error: function () {
                        self.downloadError(self.ERROR_MESSAGE);
                    }
                });
            }
        };

        self.downloadError = function(text){
            self.init();
            self.$download_progress.html(text);
        };

        self.$el.on("show show.bs.modal", self.generateDownload);
        self.$el.on("hidden hidden.bs.modal", function(){
            self.init();
        });
        self.init();
    };
}());
