hqDefine("reports/js/submit_history", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
    $(function () {
        if (document.location.href.match(/reports\/submit_history/)) {
            $(document).on('click', 'td.view-form-link', function () {
                kissAnalytics.track.event("Clicked View Form in Submit History Report");
            });
            var userTypes = initialPageData.get('user_types');
            $(document).on('click', 'button#apply-filters', function () {
                kissAnalytics.track.event("Clicked Apply",
                    {"filters": _.map(_.find($('#paramSelectorForm').serializeArray(),
                            function (obj) { return obj.name === "emw"; }).value.split(','),
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
