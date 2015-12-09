var HQExportDownloader = function (options) {
    var self = this;
    self.downloadLink = options.dowloadLink || '.export-action-download';
    self.modal = options.modal || "#export-download-status";
    self.loadingIndicator = options.loadingIndicator || ".loading-indicator";
    self.loadedData = options.loadedData || ".loaded-data";

    self.init = function () {
        $(function () {
            $(self.downloadLink).click(function () {
                var $modal = $(self.modal);
                var caseType = $(this).attr("data-caseType");
                $modal.find(self.loadingIndicator).removeClass('hide');
                $modal.find(self.loadedData).empty();
                $modal.find('.modal-header h3 span').text($(this).data("formname"));

                $.getJSON($(this).data('dlocation'), function (d) {
                    var autoRefresh = true;
                    var pollDownloader = function () {
                        if (autoRefresh && $('#ready_'+d.download_id).length === 0)
                        {
                            $.get(d.download_url, function(data) {
                                $modal.find(self.loadedData).html(data);
                                self.setUpEventTracking(caseType);
                                if (autoRefresh) {
                                    setTimeout(pollDownloader, 2000);
                                }
                            });
                        } else {
                            $modal.find(self.loadingIndicator).addClass('hide');
                            autoRefresh = false;
                        }
                    };
                    $(self.modal).on('hide', function () {
                        autoRefresh = false;
                    });
                    pollDownloader();
                });


            });
        });
    };
    /**
     * Attach a click event handler to the download modal "download" button that
     * notifies google of the download event.
     */
    self.setUpEventTracking = function(caseType){
        var downloadButton = $(self.modal).find(self.loadedData).find("a.btn.btn-primary").first();
        if (downloadButton.length) {
            gaTrackLink(downloadButton, "Download Case Export", "Download Custom Case Export", caseType);
        }
    };
};
