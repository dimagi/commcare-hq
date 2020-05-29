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
    var log = function (message) {
        console.log("[" + (new Date()).toLocaleTimeString() + "] " + message);
    };

    $(function () {
        var timeout = initialPageData.get('secure_timeout') * 60 * 1000,    // convert from minutes to milliseconds
            $modal = $("#inactivityModal"),     // won't be present on app preview or pages without a domain
            $warningModal = $("#inactivityWarningModal"),
            keyboardOrMouseActive = false,
            warningActive = false;

        if (timeout === undefined || !$modal.length) {
            return;
        }
log("page loaded, timeout  length is " + timeout / 1000 / 60 + " minutes");

        /**
          * Determine when to poll next. Poll more frequently as expiration approaches, to
          * increase the chance the modal pops up before the user takes an action and gets rejected.
          */
        var calculateDelayAndWarn = function (lastRequest) {
            var millisLeft = timeout;
            if (lastRequest) {
                millisLeft = timeout - (new Date() - new Date(lastRequest));
log("last request was " + lastRequest + ", so there are " + (millisLeft / 1000 / 60) + " minutes left in the session");
            } else {
log("no last request, so there are " + (millisLeft / 1000 / 60) + " minutes left in the session");
            }

            // Last 30 seconds, ping every 3 seconds
            if (millisLeft < 30 * 1000) {
                showWarningModal();
log("show warning and poll again in 3 sec");
                return 3000;
            }

            // Last 2 minutes, ping every ten seconds
            if (millisLeft < 2 * 60 * 1000) {
                showWarningModal();
log("show warning and poll again in 10 sec");
                return 10 * 1000;
            }

            // We have time, ping when 2 minutes from expiring
log("poll again in " + (millisLeft - 2 * 60 * 1000) / 1000 / 60 + " minutes");
            return millisLeft - 2 * 60 * 1000;
        };

        var showWarningModal = function () {
            warningActive = true;
            if (!keyboardOrMouseActive) {
                $warningModal.modal('show');
            }
        };

        var hideWarningModal = function () {
            $warningModal.modal('hide');
        };

        var pollToShowModal = function () {
log("polling HQ's ping_login to decide about showing modal");
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    if (!data.success) {
log("ping_login failed, showing login modal");
                        var $body = $modal.find(".modal-body");
                        $modal.on('shown.bs.modal', function () {
                            var content = _.template('<iframe src="<%= src %>" height="<%= height %>" width="<%= width %>" style="border: none;"></iframe>')({
                                src: initialPageData.reverse('iframe_login') + "?next=" + initialPageData.reverse('iframe_login_new_window'),
                                width: $body.width(),
                                height: $body.height() - 10,
                            });
                            $body.html(content);
                            $body.find("iframe").on("load", pollToHideModal);
                        });
                        $body.html('<h1 class="text-center"><i class="fa fa-spinner fa-spin"></i></h1>');
                        hideWarningModal();
                        $modal.modal({backdrop: 'static', keyboard: false});
                    } else {
log("ping_login succeeded, time to re-calculate when the next poll should be, data was " + JSON.stringify(data));
                        _.delay(pollToShowModal, calculateDelayAndWarn(data.last_request));
                    }
                },
            });
        };

        var pollToHideModal = function (e) {
log("polling HQ's ping_login to decide about hiding modal");
            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                url: initialPageData.reverse('ping_login'),
                type: 'GET',
                success: function (data) {
                    $button.enableButton();
                    var error = "";
                    if (data.success) {
                        if (data.username !== initialPageData.get('secure_timeout_username')) {
                            error = gettext(_.template("Please log in as <%= username %>"))({
                                username: initialPageData.get('secure_timeout_username'),
                            });
                        }
                    } else {
                        error = gettext("Could not authenticate, please log in and try again");
                    }

                    if (error) {
                        $button.removeClass("btn-default").addClass("btn-danger");
                        $button.text(gettext("Could not authenticate, please log in and try again"));
                    } else {
                        $modal.modal('hide');
                        $button.text(gettext("Done"));
                        _.delay(pollToShowModal, calculateDelayAndWarn());
                    }
                },
            });
        };

        var extendSession = function (e) {
            var $button = $(e.currentTarget);
            $button.disableButton();
            warningActive = false;
            $.ajax({
                url: initialPageData.reverse('bsd_license'),  // Public view that will trigger session activity
                type: 'GET',
                success: function () {
                    $button.enableButton();
                    hideWarningModal();
                },
            });
        };

        $modal.find(".modal-footer .dismiss-button").click(pollToHideModal);
        $warningModal.find(".modal-footer .dismiss-button").click(extendSession);
        $warningModal.on('shown.bs.modal', function () {
            $warningModal.find(".btn-primary").focus();
        });

        // Keep track of when user is actively typing
        $("body").on("keypress", _.throttle(function () {
            keyboardOrMouseActive = true;
        }, 100, {trailing: false}));
        $("body").on("keypress", _.debounce(function () {
            keyboardOrMouseActive = false;
            if (warningActive) {
                showWarningModal();
            }
        }, 500));

        // Start polling
        _.delay(pollToShowModal, calculateDelayAndWarn());
    });

    return 1;
});
