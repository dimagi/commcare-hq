hqDefine('locations/js/import', [
    'jquery',
    'analytix/js/google',
    'commtrack/js/location_bulk_upload_file',
], function(
    $,
    googleAnalytics
) {
    $(function() {
        googleAnalytics.track.click($('#download_link'), 'Organization Structure', 'Bulk Import', 'Download');
        $("button[type='submit']").click(function() {
            googleAnalytics.track.event('Organization Structure', 'Bulk Import', 'Upload');
        });
    });
});
