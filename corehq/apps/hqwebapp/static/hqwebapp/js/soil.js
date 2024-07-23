"use strict";
hqDefine("hqwebapp/js/soil", [
    "jquery",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    initialPageData
) {
    $(function () {
        var downloadId = initialPageData.get("download_id"),
            autoRefresh = '',
            pollDownloader = function () {
                if (!$('#ready_' + downloadId).length) {
                    $.ajax(initialPageData.get("poll_url"), {
                        success: function (data) {
                            $("#display_" + downloadId).html(data);
                        },
                        error: function (data) {
                            var message = initialPageData.get("error_text");
                            if (data.responseText !== undefined && data.responseText !== '') {
                                message = data.responseText;
                            }
                            $("#display_" + downloadId).html('<p class="alert alert-danger">' + message + '</p>');
                            clearInterval(autoRefresh);
                        },
                    });
                } else {
                    clearInterval(autoRefresh);
                }
            };
        pollDownloader();
        autoRefresh = setInterval(pollDownloader, 2000);
    });
});
