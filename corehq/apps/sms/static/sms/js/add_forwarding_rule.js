hqDefine('sms/js/add_forwarding_rule',[
    "jquery",
], function ($) {
    function toggleKeyword() {
        if ($("#id_forward_type").val() === "KEYWORD") {
            $("#keyword_row").removeClass('hide');
        } else {
            $("#keyword_row").addClass('hide');
        }
    }
    $(function () {
        toggleKeyword();
        $("#id_forward_type").change(function () {
            toggleKeyword();
        });
    });
});
