hqDefine("enterprise/js/enterprise_dashboard", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'analytix/js/kissmetrix',
    'hqwebapp/js/bootstrap3/hq.helpers',
], function (
    $,
    initialPageData,
    alertUser,
    kissmetrics
) {
    $(function () {
        kissmetrics.track.event("[Enterprise Dashboard] Visited page");
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

            $element.find(".btn-primary").click(function () {
                kissmetrics.track.event("[Enterprise Dashboard] Clicked Email Report for " + slug);
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
