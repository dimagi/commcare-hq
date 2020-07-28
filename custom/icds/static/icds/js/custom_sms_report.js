hqDefine("icds/js/custom_sms_report",[
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/daterangepicker.config', //createBootstrap3DefaultDateRangePicker
], function (
    $,
    initialPageData
) {
    var $el = $('#date_range_selector');
    var $startDate = $('#report_start_date');
    var $endDate = $('#report_end_date');
    var $submitBtn = $('#request_report');
    if ( initialPageData.get('disable_submit')) {
        $submitBtn.attr('disabled', true);
    }
    $el.createBootstrap3DefaultDateRangePicker();
    $el.on('apply change', function () {
        var separator = $().getDateRangeSeparator();
        var dates = $el.val().split(separator);
        $startDate.val(dates[0]);
        $endDate.val(dates[1]);
    });
});