hqDefine("reports/js/case_details.js", function() {
    $(function() {
        $('#close_case').submit(function() {
            ga_track_event('Edit Data', 'Close Case', '-', {
                'hitCallback': function () {
                    document.getElementById('close_case').submit();
                },
            });
            return false;
        });
    });
});
