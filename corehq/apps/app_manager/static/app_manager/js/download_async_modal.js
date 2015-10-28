$(function(){
    "use strict";

    COMMCAREHQ.AsyncDownloader = function($el, download_url){
        var self = this;
        self.POLL_FREQUENCY = 1500; //ms
        self.ERROR_MESSAGE = "Sorry, something went wrong with the download. " +
                             "If you see this repeatedly please report an issue.";
        self.download_url = download_url;

        self.$el = $el;
        self.el_id = $el.attr("id");
        self.$download_progress = self.$el.find("#" + self.el_id + "-download-progress");
        self.$downloading = self.$el.find("#" + self.el_id + "-downloading");
        self.downloadGenerated = false;

        self.init = function(){
            self.$download_progress.addClass("hide");
            self.$downloading.removeClass("hide");
        };

        self.startPollDownloadStatus = function(data){
            var keep_polling = true,
                ready_id = 'ready_' + data.download_id,
                error_id = 'error_' + data.download_id;
            var pollDownloadStatus = function(){
                if (keep_polling) {
                    $.ajax({
                        url: data.download_url,
                        success: function (resp) {
                            if (resp.trim().length) {
                                self.$downloading.addClass("hide");
                                self.$download_progress.html(resp).removeClass("hide");
                                var done = _.find([ready_id, error_id], function(el_id) {
                                    return resp.indexOf(el_id) > 0;
                                });
                                if (done) {
                                    keep_polling = false;
                                }
                            }
                            if (keep_polling) {
                                setTimeout(pollDownloadStatus, self.POLL_FREQUENCY);
                            }
                        },
                        error: function (resp) {
                            self.downloadError(resp.responseText);
                        }
                    });
                }
            };


            self.$el.on("hidden hidden.bs.modal", function(){
                keep_polling = false;
                self.init();
            });

            pollDownloadStatus();
        };

        self.generateDownload = function(){
            // prevent multiple calls
            if (!self.downloadGenerated) {
                $.ajax({
                    url: self.download_url,
                    type: "GET",
                    dataType: "json",
                    success: function (data) {
                        self.startPollDownloadStatus(data);
                    },
                    error: function () {
                        self.downloadError(self.ERROR_MESSAGE);
                    }
                });
                self.downloadGenerated = true;
            }
        };

        self.downloadError = function(text){
            self.$downloading.addClass("hide");
            self.$download_progress.removeClass("hide").html(text);
        };

        self.$el.on("show show.bs.modal", self.generateDownload);
        self.init();
    };
}());
