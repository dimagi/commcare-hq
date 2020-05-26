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
            $modal = $("#inactivityModal");     // won't be present on app preview or pages without a domain

        if (timeout === undefined || !$modal.length) {
            return;
        }

        var pollToShowModal = function () {
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    if (!data.success) {
                        clearInterval(interval);
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
                        $body.html('<h1 class="text-center"><i class="fa fa-spinner fa-spin"></i></h1>');
                        $modal.modal({backdrop: 'static', keyboard: false});
                    }
                },
            });
        };

        var pollToHideModal = function (e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    $button.enableButton();
                    if (data.success) {
                        $modal.modal('hide');
                        $button.text(gettext("Done"));
                        // TODO: restart interval
                    } else {
                        $button.removeClass("btn-primary").addClass("btn-danger");
                        $button.text(gettext("Could not authenticate, please log in and try again"));
                    }
                },
            });
        };

        interval = setInterval(pollToShowModal, timeout * 60 * 1000);    // convert from minutes to milliseconds

        $modal.find(".modal-footer .dismiss-button").click(pollToHideModal);
    });

    return 1;
});
