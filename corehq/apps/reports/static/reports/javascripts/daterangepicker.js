
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

        $('[name="daterangepicker_start"]').removeAttr("disabled");
        $('[name="daterangepicker_end"]').removeAttr("disabled");

        $('.daterangepicker_start_input').toggle($('.ranges ul li:nth-child(4)').attr('class'));
        $('.daterangepicker_end_input').toggle($('.ranges ul li:nth-child(4)').attr('class'));

        $('.ranges ul li:nth-child(4)').click(function() {
            $('.daterangepicker_start_input').show();
            $('.daterangepicker_end_input').show();
        });

        $('.ranges ul li:not(:nth-child(4))').click(function() {
            $('.daterangepicker_start_input').hide();
            $('.daterangepicker_end_input').hide();
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
