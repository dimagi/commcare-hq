hqDefine("reports/js/submit_history", ['jquery', 'analytix/js/kissmetrix', 'hqwebapp/js/initial_page_data'],
    function ($, kissAnalytics, initialPageData) {
        $(function () {
            if (document.location.href.match(/reports\/submit_history/)) {
                $(document).on('click', 'td.view-form-link', function () {
                    kissAnalytics.track.event("Clicked View Form in Submit History Report");
                });
                var userTypes = initialPageData.get('user_types');
                var selector = "#paramSelectorForm select[name='emw']";
                $(document).on('click', '#apply-filters', function () {
                    var typePrefix = "t__",
                        userPrefix = "u__";
                    kissAnalytics.track.event("[Submit History Report] Clicked Apply", {
                        "filters": _.map($(selector).select2("data"), function (item) {
                            if (item.id.startsWith(typePrefix)) {
                                return userTypes[item.id.substring(typePrefix.length)];
                            }
                            else if (item.id.startsWith(userPrefix)) {
                                // TODO: when there's an initial value, the is_active flag isn't part of it,
                                // so .select2('data') doesn't pick it up and the worker is always marked as deactivated
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
