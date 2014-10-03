
$(function() {
    'use strict';

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
            maxDate: now,
            ranges: ranges,
            separator: separator
        });
    };
});
