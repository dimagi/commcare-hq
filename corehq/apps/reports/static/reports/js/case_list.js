hqDefine("reports/js/case_list", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
    $(function () {
        if (document.location.href.match(/reports\/case_list/)) {
            $(document).on('click', 'td.case-name-link', function () {
                kissAnalytics.track.event("Clicked Case Name in Case List Report");
            });
            var userTypes = initialPageData.get('user_types');
            $(document).on('click', '#apply-filters', function () {
                kissAnalytics.track.event("Clicked Apply",
                    {"filters": _.map(_.find($('#paramSelectorForm').serializeArray(),
                            function (obj) { return obj.name === "case_list_filter"; }).value.split(','),
                            function (item) {
                                if (item[0] === "t") { return userTypes[item.substring(3)]; }
                                else { return item; }
                            }
                    )}
                );
            });
        }
    });
});
