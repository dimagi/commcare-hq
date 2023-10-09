hqDefine("geospatial/js/case_grouping_map",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/bootstrap3/components.ko", // for pagination
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';

    $(function () {
        $(document).ajaxComplete(function (event, xhr, settings) {
            const isAfterReportLoad = settings.url.includes('geospatial/async/case_grouping_map/');
            if (isAfterReportLoad) {
                return;
            }

            const isAfterDataLoad = settings.url.includes('geospatial/json/case_grouping_map/');
            if (!isAfterDataLoad) {
                return;
            }


        });
    });

});