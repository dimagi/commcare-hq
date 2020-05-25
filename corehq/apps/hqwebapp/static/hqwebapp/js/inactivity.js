/*
 *  TODO
 */
hqDefine('hqwebapp/js/activity', [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    $(function () {
        var interval = 60 * 1000;
        setInterval(function () {
            $.ajax({
                url: initialPageData.reverse('cloudcare_ping'),
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
