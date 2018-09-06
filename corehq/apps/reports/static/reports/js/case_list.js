hqDefine("reports/js/case_list", ['jquery', 'analytix/js/kissmetrix'], function ($, kissAnalytics) {
    $(function () {
        if (document.location.href.match(/reports\/case_list/)) {
            $(document).on('click', 'td.case-name-link', function () {
                kissAnalytics.track.event("Clicked Case Name in Case List Report");
            });
        }
    });
});
