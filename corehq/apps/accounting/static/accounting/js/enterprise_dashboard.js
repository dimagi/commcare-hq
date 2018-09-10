hqDefine("accounting/js/enterprise_dashboard", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/hq.helpers',
], function (
    $,
    initialPageData,
    alertUser
) {
    $(function () {
        $(".report-panel").each(function () {
            var $element = $(this),
                slug = $element.data("slug");

            // Load total
            $.ajax({
                url: initialPageData.reverse("enterprise_dashboard_total", slug),
                success: function (data) {
                    $element.find(".total").html(Number(data.total).toLocaleString());
                },
            });

            $element.find(".btn-success").click(function () {
                var $button = $(this);
                $button.disableButton();
                $.ajax({
                    url: initialPageData.reverse("enterprise_dashboard_email", slug),
                    success: function (data) {
                        alertUser.alert_user(data.message, "success");
                        $button.enableButton();
                    },
                    error: function () {
                        alertUser.alert_user(gettext("Error sending email, please try again or report an issue if this persists."), "danger");
                        $button.enableButton();
                    },
                });
            });
        });
    });
});
