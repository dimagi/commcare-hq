/*
 *  Handles inactvitiy timeout UI: a modal containing an iframe with the login screen,
 *  allowing users to re-login without leaving the page and losing their work.
 */
hqDefine('hqwebapp/js/inactivity', [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var timeout = initialPageData.get('secure_timeout'),
            $modal = $("#inactivityModal");  // won't be present on app preview
        if (timeout === undefined || !$modal.length) {
            return;
        }
        var interval = setInterval(function () {
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    if (!data.success) {
                        clearInterval(interval);        // TODO: restart once user is logged in
                        var $body = $modal.find(".modal-body");
                        $modal.on('shown.bs.modal', function () {
                            var content = _.template('<iframe src="<%= src %>" height="<%= height %>" width="<%= width %>" style="border: none;"></iframe>')({
                                // TODO: get rid of everything that makes login look like a full page
                                // TODO: what if user clicks on something undesireable? reset password worfklow?
                                src: initialPageData.reverse('login_new_window'),
                                width: $body.width(),
                                height: $body.height() - 10,
                            });
                            $body.html(content);
                        });
                        $modal.modal({backdrop: 'static', keyboard: false});
                    }
                },
            });
        }, timeout * 60 * 1000);    // convert from minutes to milliseconds
    });

    return 1;
});
