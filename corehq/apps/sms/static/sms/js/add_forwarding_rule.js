hqDefine('sms/js/add_forwarding_rule', function() {
    function toggle_keyword() {
        if($("#id_forward_type").val() == "KEYWORD") {
            $("#keyword_row").removeClass('hide');
        } else {
            $("#keyword_row").addClass('hide');
        }
    }
    $(function(){
        toggle_keyword();
        $("#id_forward_type").change(function() {
            toggle_keyword();
        });
    });
});
