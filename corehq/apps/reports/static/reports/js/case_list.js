hqDefine("reports/js/case_list", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
        $(function () {
            if (document.location.href.match(/reports\/case_list/)) {
                $(document).on('click', 'td.case-name-link', function () {
                    kissAnalytics.track.event("Clicked Case Name in Case List Report");
                });
                var userTypes = initialPageData.get('user_types');
                var selector = "#paramSelectorForm select[name='case_list_filter']";
                $(document).on('click', '#apply-filters', function () {
                    var typePrefix = "t__",
                        userPrefix = "u__";
                    kissAnalytics.track.event("[Case List Report] Clicked Apply", {
                        "filters": _.map($(selector).select2("data"), function (item) {
                            if (item.id.startsWith(typePrefix)) {
                                return userTypes[item.id.substring(typePrefix.length)];
                            }
                            else if (item.id.startsWith(userPrefix)) {
                                // TODO: same issue as submit_history.js
                                if (item.is_active) {
                                    return item.id + " [Active]";
                                } else {
                                    return item.id + " [Deactivated]";
                                }
                            }
                            else {
                                return item.id;
                            }
                        }).join(),
                    });
                });
            }
        });
    });
