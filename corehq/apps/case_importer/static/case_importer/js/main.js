hqDefine("case_importer/js/main", [
    'jquery',
    'underscore',
    'case_importer/js/import_history',
], function(
    $,
    _,
    importHistory
) {
    $(function () {
        // First page: recent uploads list
        var $recentUploads = $('#recent-uploads');
        if ($recentUploads.length) {
            var recentUploads = importHistory.recentUploadsModel();
            $('#recent-uploads').koApplyBindings(recentUploads);
            _.delay(recentUploads.fetchCaseUploads);
        }
    });
});
