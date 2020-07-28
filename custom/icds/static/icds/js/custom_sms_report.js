hqDefine("icds/js/custom_sms_report",[
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/daterangepicker.config', //createBootstrap3DefaultDateRangePicker
], function (
    $,
    initial_page_data
) {
    var $el = $('#date_range_selector');
    var $startDate = $('#report_start_date');
    var $endDate = $('#report_end_date');
    var $submit_btn = $('#request_report');
    if(initial_page_data.get('disable_submit'))
        $submit_btn.attr('disabled', true);
    $el.createBootstrap3DefaultDateRangePicker();
    $el.on('apply change', function () {
        var separator = $().getDateRangeSeparator();
        var dates = $el.val().split(separator);
        $startDate.val(dates[0]);
        $endDate.val(dates[1]);
    });
});