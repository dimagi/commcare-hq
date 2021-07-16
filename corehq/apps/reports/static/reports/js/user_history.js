hqDefine("reports/js/user_history", [
    'jquery',
], function (
    $
) {
    $(function () {
        if (document.location.href.match(/reports\/user_history/)) {
            $(document).on('click', '.see-all-link', function () {
                var $container = $(this).closest(".see-all");
                $container.children(".see-all-primary, .see-all-link").addClass("hide");
                $container.children(".see-all-complete").removeClass("hide");
                $("#report_table_user_history").DataTable().columns.adjust();
            });
        }
    });
});
