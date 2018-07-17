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
        // Widgets used on multiple pages
        $('#back_button').click(function() {
            history.back();
            return false;
        });
        $('#back_breadcrumb').click(function(e) {
            e.preventDefault();
            history.back();
            return false;
        });

        // First page: recent uploads list
        var $recentUploads = $('#recent-uploads');
        if ($recentUploads.length) {
            var recentUploads = importHistory.recentUploadsModel();
            $('#recent-uploads').koApplyBindings(recentUploads);
            _.delay(recentUploads.fetchCaseUploads);
        }
    });
});
