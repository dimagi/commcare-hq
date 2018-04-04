hqDefine("soil/js/file_download", function() {
    $(function () {
        var autoRefresh = '';
        var pollDownloader = function () {
            var downloadId = $(".downloader_container[data-download-id]").data("downloadId");
console.log("id=" + downloadId);
            if ($('#ready_' + downloadId).length == 0)
	        {
                $.ajax("{% url 'ajax_job_poll' download_id %}", {
                    success: function(data) {
                        $("#display_" + downloadId).html(data);
                    },
                    error: function(data) {
                        $("#display_" + downloadId).html(data.responseText);
                        clearInterval(autoRefresh);
                    }
                });
	        } else {
	            clearInterval(autoRefresh);
	        }
        };
        autoRefresh = setInterval(pollDownloader, 2000);
    });
});
