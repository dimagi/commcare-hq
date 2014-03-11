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
                $modal.find(self.loadingIndicator).removeClass('hide');
                $modal.find(self.loadedData).empty();
                $modal.find('.modal-header h3 span').text($(this).data("formname"));

                $.getJSON($(this).data('dlocation'), function (d) {
                    var autoRefresh = '';
                    var pollDownloader = function () {
                        if ($('#ready_'+d.download_id).length == 0)
                        {
                            $.get(d.download_url, function(data) {
                                $modal.find(self.loadedData).html(data);
                            });
                        } else {
                            $modal.find(self.loadingIndicator).addClass('hide');
                            clearInterval(autoRefresh);
                        }
                    };
                    $(self.modal).on('hide', function () {
                        clearInterval(autoRefresh);
                    });
                    autoRefresh = setInterval(pollDownloader, 2000);
                });


            });
        });
    };
};
