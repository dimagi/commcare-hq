import $ from 'jquery';

$(function () {
    var autoRefresh = '';
    var pollDownloader = function () {
        var $downloadContainer = $(".downloader_container[data-download-id]"),
            downloadId = $downloadContainer.data("downloadId");
        if (!$('#ready_' + downloadId).length) {
            $.ajax($downloadContainer.data("url"), {
                success: function (data) {
                    $("#display_" + downloadId).html(data);
                },
                error: function (data) {
                    $("#display_" + downloadId).html(data.responseText);
                    clearInterval(autoRefresh);
                },
            });
        } else {
            clearInterval(autoRefresh);
        }
    };
    autoRefresh = setInterval(pollDownloader, 2000);
});
