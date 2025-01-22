hqDefine('app_manager/js/import_app', [
    'jquery',
    'app_manager/js/apps_base',     // TODO: is this necessary?
    'commcarehq',
], function (
    $,
) {
    $(function () {
        $(".historyBack").click(function () {
            history.back();
            return false;
        });
    });
});
