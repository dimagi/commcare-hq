/*
 *  TODO
 */
hqDefine('hqwebapp/js/inactivity', [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    $(function () {
        var interval = 60 * 1000;       // TODO: get timeout from domain
        setInterval(function () {
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    if (!data.success) {
                        $("#inactivityModal").modal('show');
                    }
                },
            });
        }, interval);
    });

    return 1;
});
