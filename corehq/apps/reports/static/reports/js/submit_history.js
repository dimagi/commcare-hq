hqDefine("reports/js/submit_history", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
        $(function () {
            if (document.location.href.match(/reports\/submit_history/)) {
                $(document).on('click', 'td.view-form-link', function () {
                    kissAnalytics.track.event("Clicked View Form in Submit History Report");
                });
                var userTypes = initialPageData.get('user_types');
                var selector = "#paramSelectorForm input[name='emw']";
                $(document).on('click', '#apply-filters', function () {
                    kissAnalytics.track.event("[Submit History Report] Clicked Apply",
                        {"filters": _.map($(selector).val().split(','),
                            function (item, index) {
                                if (item.substring(0,3) === "t__") { return userTypes[item.substring(3)]; }
                                else if (item.substring(0,3) === "u__") {
                                    if ($(selector).select2("data")[index].is_active)
                                    {return item + " [Active]"; }
                                    else
                                    {return item + " [Deactivated]"; }
                                }
                                else { return item; }
                            }
                        ).join()}
                    );
                });
            }
        });
    });
