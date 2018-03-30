hqDefine('locations/js/import', function() {
    $(function() {
        hqImport('analytix/js/google').track.click($('#download_link'), 'Organization Structure', 'Bulk Import', 'Download');
        $("button[type='submit']").click(function() {
            hqImport('analytix/js/google').track.event('Organization Structure', 'Bulk Import', 'Upload');
        });
    });
});
