hqDefine('app_manager/js/download_async_modal', [
    'jquery',
    'underscore',
], function (
    $,
    _
) {
    var asyncDownloader = function ($el) {
        "use strict";
        var self = {};
        self.POLL_FREQUENCY = 1500; //ms
        self.ERROR_MESSAGE = gettext("Sorry, something went wrong with the download. " +
                             "If you see this repeatedly please report an issue.");

        self.$el = $el;
        self.elId = $el.attr("id");
        self.$download_progress = self.$el.find("#" + self.elId + "-download-progress");
        self.$downloading = self.$el.find("#" + self.elId + "-downloading");

        self.init = function () {
            self.download_in_progress = false;
            self.download_poll_url = null;
            self.download_poll_id = null;
            self.$download_progress.addClass("hide");
            self.$downloading.removeClass("hide");
            self.$el.removeClass("full-screen-modal");
        };

        self.pollDownloadStatus = function () {
            if (self.download_in_progress) {
                $.ajax({
                    url: self.download_poll_url,
                    data: {'message': self.ready_message},
                    success: function (resp) {
                        self.updateProgress(resp);
                        if (!self.isDone(resp)) {
                            setTimeout(self.pollDownloadStatus, self.POLL_FREQUENCY);
                        } else {
                            self.download_in_progress = false;
                        }
                    },
                    error: function (resp) {
                        self.downloadError(resp.responseText);
                    },
                });
            }
        };

        self.updateProgress = function (progressResponse) {
            if (progressResponse.trim().length) {
                self.$downloading.addClass("hide");
                self.$download_progress.html(progressResponse).removeClass("hide");
            }
        };

        self.isDone = function (progressResponse) {
            var readyId = 'ready_' + self.download_poll_id,
                errorId = 'error_' + self.download_poll_id;
            return progressResponse &&
                progressResponse.trim().length &&
                _.any([readyId, errorId], function (elId) {
                    return progressResponse.indexOf(elId) >= 0;
                });
        };

        self.generateDownload = function (downloadUrl, params) {
            // prevent multiple calls
            if (!self.download_in_progress) {
                self.download_in_progress = true;
                $.ajax({
                    url: downloadUrl,
                    type: "GET",
                    data: params,
                    dataType: "json",
                    success: function (data) {
                        self.download_poll_url = data.download_url;
                        self.download_poll_id = data.download_id;
                        if (data.message) {
                            self.ready_message = data.message;
                        }
                        self.pollDownloadStatus();
                    },
                    error: function () {
                        self.downloadError(self.ERROR_MESSAGE);
                    },
                });
            }
        };

        self.downloadError = function (text) {
            self.init();
            self.$download_progress.html(text);
            self.$download_progress.removeClass("hide");
            self.$downloading.addClass("hide");
            self.$el.addClass("full-screen-modal");     // allow scrolling in case of many errors
        };

        self.$el.on("hidden hidden.bs.modal", function () {
            self.init();
        });

        self.init();

        return self;
    };

    var downloadApplicationZip = function () {
        var $modal = $(".download-async-modal"),
            downloader = asyncDownloader($modal);
        downloader.generateDownload($modal.data("url"));
    };
    $(document).on('click','.download-zip',downloadApplicationZip);

    return {
        asyncDownloader: asyncDownloader,
    };
});
