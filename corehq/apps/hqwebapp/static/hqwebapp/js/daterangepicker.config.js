hqDefine("hqwebapp/js/daterangepicker.config", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'moment/moment',
    'bootstrap-daterangepicker/daterangepicker',
], function (
    $,
    _,
    initialPageData,
    moment
) {
    'use strict';

    $.fn.getDateRangeSeparator = function () {
        return ' to ';
    };
    $.fn.createDateRangePicker = function (
        range_labels, separator, startdate, enddate
    ) {
        var ranges = {};
        ranges[range_labels.last_7_days] = [
            moment().subtract('7', 'days').startOf('days'),
        ];

        ranges[range_labels.last_month] = [
            moment().subtract('1', 'months').startOf('month'),
            moment().subtract('1', 'months').endOf('month'),
        ];

        ranges[range_labels.last_30_days] = [
            moment().subtract('30', 'days').startOf('days'),
        ];
        var config = {
            showDropdowns: true,
            ranges: ranges,
            timePicker: false,
            locale: {
                format: 'YYYY-MM-DD',
                separator: separator,
            },
        };
        var hasStartAndEndDate = !_.isEmpty(startdate) && !_.isEmpty(enddate);
        if (hasStartAndEndDate) {
            config.startDate = new Date(startdate);
            config.endDate = new Date(enddate);
        }

        $(this).daterangepicker(config);

        // UCRs
        if (initialPageData.get('daterangepicker-show-clear')) {
            // Change 'Cancel' button text to 'Clear'
            var $el = $(this);
            config.locale.cancelLabel = gettext('Clear');
            $el.daterangepicker(config);

            // Add clearing functionality
            $el.on('cancel.daterangepicker', function () {
                $el.val(gettext("Show All Dates")).change();

                // Clear startdate and enddate filters
                var filter_id = $(this)[0].getAttribute("name");
                var filter_id_start = filter_id + "-start";
                var filter_id_end = filter_id + "-end";
                if (document.getElementById(filter_id_start) && document.getElementById(filter_id_end)) {
                    document.getElementById(filter_id_start).setAttribute("value", "");
                    document.getElementById(filter_id_end).setAttribute("value", "");
                }
            });
        }

        if (! hasStartAndEndDate) {
            $(this).val("");
        }
    };
    $.fn.createBootstrap3DefaultDateRangePicker = function () {
        this.createDateRangePicker(
            {
                last_7_days: 'Last 7 Days',
                last_month: 'Last Month',
                last_30_days: 'Last 30 Days',
            },
            this.getDateRangeSeparator()
        );
    };
});
