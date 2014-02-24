
$(function() {
    'use strict';

    $.fn.createDateRangePicker = function(range_labels, separator) {
        var now = moment();
        var ranges = {};

        ranges[range_labels['year_to_date']] = [
            moment().subtract('years', '1').startOf('year'),
            now
        ];
        ranges[range_labels['last_month']] = [
            moment().subtract('months', '1').startOf('month'),
            moment().subtract('months', '1').endOf('month')
        ];
        ranges[range_labels['last_quarter']] = [
            moment().subtract('years', '1').endOf('year').subtract('months', '2').startOf('month'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_two_quarters']] = [
            moment().subtract('years', '1').endOf('year').subtract('months', '5').startOf('month'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_three_quarters']] = [
            moment().subtract('years', '1').endOf('year').subtract('months', '8').startOf('month'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_year']] = [
            moment().subtract('years', '1').startOf('year'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_two_years']] = [
            moment().subtract('years', '2').startOf('year'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_three_years']] = [
            moment().subtract('years', '3').startOf('year'),
            moment().subtract('years', '1').endOf('year')
        ];
        ranges[range_labels['last_four_years']] = [
            moment().subtract('years', '4').startOf('year'),
            moment().subtract('years', '1').endOf('year')
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
