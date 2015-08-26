
$(function() {
    'use strict';
    $.fn.getDateRangeSeparator = function () {
        return ' to ';
    };
    $.fn.createDateRangePicker = function(range_labels, separator) {
        var now = moment();
        var ranges = {};
        ranges[range_labels['last_7_days']] = [
            moment().subtract('days', '7').startOf('days')
        ];

        ranges[range_labels['last_month']] = [
            moment().subtract('months', '1').startOf('month'),
            moment().subtract('months', '1').endOf('month')
        ];

        ranges[range_labels['last_30_days']] = [
            moment().subtract('days', '30').startOf('days')
        ];

        $(this).daterangepicker({
            format: 'YYYY-MM-DD',
            showDropdowns: true,
            ranges: ranges,
            separator: separator
        });
    };
    $.fn.createDefaultDateRangePicker = function () {
        this.createDateRangePicker(
            {
                'last_7_days': 'Last 7 Days',
                'last_month': 'Last Month',
                'last_30_days': 'Last 30 Days'
            },
            this.getDateRangeSeparator()
        )
    };

});
