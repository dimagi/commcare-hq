
hqDefine("scheduling/js/conditional_alert_main", [
    'data_interfaces/js/case_rule_criteria',
    'scheduling/js/create_schedule.ko',
    'data_interfaces/js/make_read_only',
], function () {
    $("#basic_continue").on('click', function () {
        if ($("#id_conditional-alert-name").val().trim()) {
            // remove error message
            $("#required_error_message").addClass('hidden');
            // move to next tab
            $("#rule-nav").removeClass('hidden');
            $("a[href='#rule']").trigger('click');
        } else {
            // show error message
            $("#required_error_message").removeClass('hidden');
            // hide following tabs
            $("#rule-nav").addClass('hidden');
            $("#schedule-nav").addClass('hidden');
        }
    });
    $("#criteria_continue").on('click', function () {
        if ($("#id_criteria-case_type").val()) {
            // remove error message
            $("#required_error_message").addClass('hidden');
            // move to next tab
            $("#schedule-nav").removeClass('hidden');
            $("a[href='#schedule']").trigger('click');
        } else {
            // show error message
            $("required_error_message").removeClass('hidden');
            // hide following tab
            $("#schedule-nav").addClass('hidden');
        }
    });
});