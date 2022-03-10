hqDefine('app_manager/js/import_app', function () {
    $(function () {
        $(".historyBack").click(function () {
            history.back();
            return false;
        });
    });
});
