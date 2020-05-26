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
        var timeout = initialPageData.get('secure_timeout') * 60 * 1000,    // convert from minutes to milliseconds
            $modal = $("#inactivityModal");     // won't be present on app preview or pages without a domain

        if (timeout === undefined || !$modal.length) {
            return;
        }

        /**
          * Determine when to poll next. Poll more frequently as expiration approaches, to
          * increase the chance the modal pops up before the user takes an action and gets rejected.
          */
        var calculateDelay = function (last_request) {
            millisLeft = timeout;
            if (last_request) {
                 millisLeft = timeout - (new Date() - new Date(last_request));
            }

            // Last 30 seconds, ping every 3 seconds
            if (millisLeft < 30 * 1000) {
                return 3000;
            }

            // Last 2 minutes, ping every ten seconds
            if (millisLeft < 2 * 60 * 1000) {
                return 10 * 1000;
            }

            // We have time, ping when 2 minutes from expiring
            return millisLeft - 2 * 60 * 1000;
        };

        var pollToShowModal = function () {
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    if (!data.success) {
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
                    } else {
                        _.delay(pollToShowModal, calculateDelay(data.last_request));
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
                        _.delay(pollToShowModal, calculateDelay());
                    } else {
                        $button.removeClass("btn-primary").addClass("btn-danger");
                        $button.text(gettext("Could not authenticate, please log in and try again"));
                    }
                },
            });
        };

        $modal.find(".modal-footer .dismiss-button").click(pollToHideModal);

        // Start polling
        _.delay(pollToShowModal, calculateDelay());
    });

    return 1;
});
