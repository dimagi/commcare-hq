hqDefine("reports/js/submit_history", ['jquery', 'analytix/js/kissmetrix'], function ($, kissAnalytics) {
    $(function () {
        if (document.location.href.match(/reports\/submit_history/)) {
            $(document).on('click', 'td.view-form-link', function () {
                kissAnalytics.track.event("Clicked View Form in Submit History Report");
            });
            $(document).on('click', 'button#apply-filters', function () {
                kissAnalytics.track.event("Clicked Apply", _.object(
                    _.pluck($('#paramSelectorForm').serializeArray(), 'name'),
                    _.pluck($('#paramSelectorForm').serializeArray(), 'value')));
            });
        }
    });
});
