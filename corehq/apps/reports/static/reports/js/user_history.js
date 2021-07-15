hqDefine("reports/js/user_history", [
    'jquery',
], function (
    $
) {
    $(function () {
        if (document.location.href.match(/reports\/user_history/)) {
            $(document).on('click', '.see-all-link', function () {
                var $link = $(this);
                $link.prev().addBack().addClass("hide");
                $link.next().removeClass("hide");
                $("#report_table_user_history").DataTable().columns.adjust();
            });
        }
    });
});
