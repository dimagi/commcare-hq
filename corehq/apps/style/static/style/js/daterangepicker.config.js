$(function () {
    'use strict';
    $.fn.getDateRangeSeparator = function () {
        return ' to ';
    };
    $.fn.createBootstrap3DateRangePicker = function(
        range_labels, separator, startdate, enddate
    ) {
        var now = moment();
        var ranges = {};
        ranges[range_labels.last_7_days] = [
            moment().subtract('7', 'days').startOf('days')
        ];

        ranges[range_labels.last_month] = [
            moment().subtract('1', 'months').startOf('month'),
            moment().subtract('1', 'months').endOf('month')
        ];

        ranges[range_labels.last_30_days] = [
            moment().subtract('30', 'days').startOf('days')
        ];
        var config = {
            showDropdowns: true,
            ranges: ranges,
            locale: {
                format: 'YYYY-MM-DD',
                separator: separator
            }
        };
        var hasStartAndEndDate = !_.isEmpty(startdate) && !_.isEmpty(enddate);
        if (hasStartAndEndDate) {
            config.startDate = new Date(startdate);
            config.endDate = new Date(enddate);
        }

        $(this).daterangepicker(config);

        if (! hasStartAndEndDate){
            $(this).val("");
        }
    };
    $.fn.createBootstrap3DefaultDateRangePicker = function () {
        this.createBootstrap3DateRangePicker(
            {
                last_7_days: 'Last 7 Days',
                last_month: 'Last Month',
                last_30_days: 'Last 30 Days'
            },
            this.getDateRangeSeparator()
        );
    };
    $.fn.createBootstrap3DefaultDateRangePicker = function () {
        this.createBootstrap3DateRangePicker(
            {
                last_7_days: 'Last 7 Days',
                last_month: 'Last Month',
                last_30_days: 'Last 30 Days'
            },
            this.getDateRangeSeparator()
        )
    };
});
