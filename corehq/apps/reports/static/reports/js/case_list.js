hqDefine("reports/js/case_list", ['jquery', 'analytix/js/kissmetrix'], function ($, kissAnalytics) {
    $(function () {
        if (document.location.href.match(/reports\/case_list/)) {
            $(document).on('click', 'td.case-name-link', function () {
                kissAnalytics.track.event("Clicked Case Name in Case List Report");
            });
            $(document).on('click', 'button#apply-filters', function () {
                kissAnalytics.track.event("Clicked Apply",
                    {"filters": _.find($('#paramSelectorForm').serializeArray(),
                            function(obj){return obj.name==="case_list_filter"}).value});
            });
        }
    });
});
