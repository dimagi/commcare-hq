hqDefine("reports/js/case_list", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
        $(function () {
            if (document.location.href.match(/reports\/case_list/)) {
                $(document).on('click', 'td.case-name-link', function () {
                    kissAnalytics.track.event("Clicked Case Name in Case List Report");
                });
                var userTypes = initialPageData.get('user_types');
                var selector = "#paramSelectorForm input[name='case_list_filter']";
                $(document).on('click', '#apply-filters', function () {
                    kissAnalytics.track.event("[Case List Report] Clicked Apply",
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
