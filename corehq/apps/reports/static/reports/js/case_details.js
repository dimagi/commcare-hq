hqDefine("reports/js/case_details", function() {
    $(function() {
        $('#close_case').submit(function() {
            hqImport('analytix/js/google').track.event('Edit Data', 'Close Case', '-', "", {}, function () {
                document.getElementById('close_case').submit();
            });
            return false;
        });
    });
});
