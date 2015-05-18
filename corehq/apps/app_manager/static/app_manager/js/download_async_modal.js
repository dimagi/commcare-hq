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

        self.init = function(){
            self.$download_progress.hide();
            self.$downloading.show();
        };

        self.startPollDownloadStatus = function(data){
            var pollDownloadStatus = function(){
                $.ajax({
                    url: data.download_url,
                    success: function(resp) {
                        if (resp.trim().length) {
                            self.$downloading.hide();
                            self.$download_progress.show().html(resp);
                            if (self.$download_progress.find(".alert-success").length) {
                                clearInterval(interval);
                            }
                        }
                    },
                    error: function(resp) {
                        self.downloadError(resp.responseText);
                        clearInterval(interval);
                    }
                });
            };

            var interval = setInterval(pollDownloadStatus, self.POLL_FREQUENCY);

            self.$el.on("hidden", function(){
                clearInterval(interval);
                self.init();
            });
        };

        self.generateDownload = function(){
            $.ajax({
                url: self.download_url,
                type: "GET",
                dataType: "json",
                success: function(data){
                    self.startPollDownloadStatus(data);
                },
                error: function(){
                    self.downloadError(self.ERROR_MESSAGE);
                }
            });
        };

        self.downloadError = function(text){
            self.$downloading.hide();
            self.$download_progress.show().html(text);
        };

        self.$el.on("show", self.generateDownload);
        self.init();
    };
}());
