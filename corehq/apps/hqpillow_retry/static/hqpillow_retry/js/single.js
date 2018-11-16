hqDefine("hqpillow_retry/js/single", ['jquery'], function ($) {
    function performAction(action) {
        if (action === 'delete') {
            var r = confirm("Are you sure you want to delete this error log?");
            if (!r) {
                return;
            }
        }
        $("input[name=action]").val(action);
        $("#actionform").submit();
    }
    $(function () {
        $.each(['reset','delete','send'], function (index, id) {
            $('#' + id).click(function () {
                performAction(id);
                return false;
            });
        });
    });
});
