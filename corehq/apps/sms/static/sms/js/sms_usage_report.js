hqDefine("sms/js/sms_usage_report",[
    'jquery',
    'knockout',
    'hqwebapp/js/daterangepicker.config', //createDateRangePicker
], function (
    $
) {
    var labels = {
        'last_7_days': 'Last 7 Days',
        'last_month': 'Last Month',
        'last_30_days': 'Last 30 Days',
    };
    var ele = $('#date_range_selector');
    ele.createDateRangePicker(labels,' to ',ele.data('startDate'),ele.data('endDate'));
});