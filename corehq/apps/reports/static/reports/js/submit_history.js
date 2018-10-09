hqImport("hqwebapp/js/initial_page_data").get('user_types')
hqDefine("reports/js/submit_history", ['jquery', 'analytix/js/kissmetrix'], function ($, kissAnalytics) {
    $(function () {
        if (document.location.href.match(/reports\/submit_history/)) {
            $(document).on('click', 'td.view-form-link', function () {
                kissAnalytics.track.event("Clicked View Form in Submit History Report");
            });
            var user_types = hqImport("hqwebapp/js/initial_page_data").get('user_types');
            $(document).on('click', 'button#apply-filters', function () {
                kissAnalytics.track.event("Clicked Apply",
                    {"filters": _.map(_.find($('#paramSelectorForm').serializeArray(),
                            function(obj)
                            {
                                return obj.name==="emw"
                            }).value.split(','),
                            function(item){if(item[0]==="t")
                            {
                                return user_types[item.substring(3)]
                            } else {
                                return item
                            }
                    })});
            });
        }
    });
});
