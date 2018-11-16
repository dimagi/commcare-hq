hqDefine("hqwebapp/js/soil", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get,
            downloadId = initialPageData("download_id"),
            autoRefresh = '',
            pollDownloader = function () {
                if (!$('#ready_' + downloadId).length) {
                    $.ajax(initialPageData("poll_url"), {
                        success: function (data) {
                            $("#display_" + downloadId).html(data);
                        },
                        error: function (data) {
                            var message = initialPageData("error_text");
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
