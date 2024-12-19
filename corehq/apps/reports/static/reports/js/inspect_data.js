hqDefine("reports/js/inspect_data", [
    'jquery',
    'underscore',
    'analytix/js/kissmetrix',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    kissAnalytics,
    initialPageData
) {
    var generateFiltersForAnalytics = function (selector, userTypes, dataLookup) {
        var typePrefix = "t__",
            userPrefix = "u__";

        return _.map($(selector).select2("data"), function (item) {
            if (item.id.startsWith(typePrefix)) {
                return userTypes[item.id.substring(typePrefix.length)];
            } else if (item.id.startsWith(userPrefix)) {
                if (item.is_active === undefined && dataLookup[item.id]) {
                    return item.id + (dataLookup[item.id].is_active ? " [Active]" : " [Deactivated]");
                } else {
                    return item.id + (item.is_active ? " [Active]" : " [Deactivated]");
                }
            } else {
                return item.id;
            }
        }).join();
    };

    $(function () {
        var userTypes = initialPageData.get('user_types');
        if (document.location.href.match(/reports\/case_list/)) {
            $(document).on('click', 'td.case-name-link', function () {
                kissAnalytics.track.event("Clicked Case Name in Case List Report");
            });
            var caseListFilterSelector = "#paramSelectorForm select[name='case_list_filter']",
                originalCaseListSelection = {};

            // This handles the initial selection if any values should be populated on page load.
            // The initial selection can pass extra data (in this case, the is_active flag) along to this
            // handler, but that extra data can't be retrieved via .select2("data"), so instead store it here.
            $(document).one('select2:select', caseListFilterSelector, function (e) {
                originalCaseListSelection = _.indexBy(e.params.data, 'id');
            });

            $(document).on('click', '#apply-filters', function () {
                kissAnalytics.track.event("[Case List Report] Clicked Apply", {
                    "filters": generateFiltersForAnalytics(caseListFilterSelector, userTypes, originalCaseListSelection),
                });
            });
        }

        if (document.location.href.match(/reports\/submit_history/)) {
            $(document).on('click', 'td.view-form-link', function () {
                kissAnalytics.track.event("Clicked View Form in Submit History Report");
            });
            var submitHistoryFilterSelector = "#paramSelectorForm select[name='emw']",
                originalSubmitHistorySelection = {};

            // See comment above for case list's select2:select handler
            $(document).one('select2:select', submitHistoryFilterSelector, function (e) {
                originalSubmitHistorySelection = _.indexBy(e.params.data, 'id');
            });

            $(document).on('click', '#apply-filters', function () {
                kissAnalytics.track.event("[Submit History Report] Clicked Apply", {
                    "filters": generateFiltersForAnalytics(submitHistoryFilterSelector, userTypes, originalSubmitHistorySelection),
                });
            });
        }
    });
});
