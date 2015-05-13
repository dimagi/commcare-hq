$(function(){
    "use strict";
    function AsyncDownloader($el, download_url){
        var self = this;
        self.POLL_FREQUENCY = 500; //ms
        self.download_url = download_url;

        self.startPollDownloadStatus = function(data){
            var pollDownloadStatus = function(){
                $.ajax({
                    url: data.download_url,
                    success: function(resp) {
                        var progress = $("#download-progress");
                        if (resp.replace(/[ \t\n]/g,'')) {
                            $("#downloading").hide();
                            progress.show().html(resp);
                            if (progress.find(".alert-success").length) {
                                clearInterval(interval);
                            }
                        }
                    },
                    error: function() {
                        // self.downloadError();
                        // clearInterval(interval);
                    }
                });
            };
            console.log(data);
            var interval = setInterval(pollDownloadStatus, self.POLL_FREQUENCY);
        };

        self.generateDownload = function(){
            $.ajax({
                url: self.download_url,
                type: 'GET',
                dataType: 'json',
                success: function(data){
                    self.startPollDownloadStatus(data);
                },
                error: function(){
                    console.log('sad face');
                }
            });
        };

        $el.on("show", self.generateDownload);
    }
    var downloader = new AsyncDownloader($("#async-file-download"), $("#async-file-download").data('download-url'));

}());


// self.downloadExcels = function(element, event) {
//     var tables = [];
//     if (self.selectedTables().length < 1)
//         return;
//     for (var i in self.selectedTables()) {
//         tables.push(self.selectedTables()[i]);
//     }
//     $("#fixture-download").modal();
//     if (tables.length > 0){
//         // POST, because a long querystring can overflow the request
//         $.ajax({
//             url: FixtureDownloadUrl,
//             type: 'POST',
//             data: {'table_ids': tables},
//             dataType: 'json',
//             success: function (response) {
//                 self.setupDownload(response);
//             },
//             error: function (response) {
//                 self.downloadError();
//             }
//         });
//     }
// };

// self.setupDownload = function (response) {
//     function poll() {
//         $.ajax({
//             url: response.download_url,
//             dataType: 'text',
//             success: function (resp) {
//                 var progress = $("#download-progress");
//                 if (resp.replace(/[ \t\n]/g,'')) {
//                     $("#downloading").hide();
//                     progress.show().html(resp);
//                     if (progress.find(".alert-success").length) {
//                         clearInterval(interval);
//                     }
//                 }
//             },
//             error: function () {
//                 self.downloadError();
//                 clearInterval(interval);
//             }
//         });
//     }
//     var interval = setInterval(poll, 2000);
//     $("#fixture-download").one("hidden", function() {
//         // stop polling if dialog is closed
//         clearInterval(interval);
//     });
//     $("#download-progress").hide();
//     $("#downloading").show();
//     poll();
// };