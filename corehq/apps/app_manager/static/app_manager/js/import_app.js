hqDefine('app_manager/js/import_app', ['jquery'], function ($) {
    $(function () {
        $(".historyBack").click(function () {
            history.back();
            return false;
        });
    });
});
