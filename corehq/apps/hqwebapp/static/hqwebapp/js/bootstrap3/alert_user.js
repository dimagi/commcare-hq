/*
    This is the knockout-based, javascript analog of messages in Django.

    Use the function `alert_user` to make a message appear on the page.

    alert_user("Awesome job!", "success");

    Parameters:
    message: The message to display
    emphasis: one of "success", "info", "warning", "danger"
    append: Set to 'true' to have the message appended to an existing message instead
       of creating a new one. NOTE: append will change the class of the alert if it is more severe
       (success < info < warning < danger).
    fadeOut: Set to 'true' to have the message automatically removed from the UI after 5s.
*/
hqDefine("hqwebapp/js/bootstrap3/alert_user", [
    "jquery",
    "knockout",
    "hqwebapp/js/bootstrap3/hq.helpers",
],
function (
    $,
    ko
) {
    var MessageAlert = function (message, tags, fadeOut) {
        var self = {
            "message": ko.observable(message),
            "alert_class": ko.observable(
                "alert fade in message-alert"
            ),
        };
        if (tags) {
            self.alert_class(self.alert_class() + " " + tags);
        }
        if (fadeOut) {
            self.timer = setTimeout(removeAlertTimerFunc(self), 5000);
        }
        self.restartTimer = function () {
            if (self.timer) {
                clearTimeout(self.timer);
                self.timer = setTimeout(removeAlertTimerFunc(self), 5000);
            }
        }
        return self;
    };

    const ViewModel = function () {
        let self = {};
        self.alerts = ko.observableArray();
        self.removeAlert = function (alertObj) {
            self.alerts.remove(alertObj);
        };

        self.fadeOut = function (element) {
            $(element).fadeOut('slow');
        };

        self.alert_user = function (message, emphasis, append, fadeOut) {
            var tags = "alert-" + emphasis;
            if (!append || self.alerts().length === 0) {
                self.alerts.push(MessageAlert(message, tags, fadeOut));
            } else {
                var alert = self.alerts()[0];
                alert.message(alert.message() + "<br>" + message);
                if (!alert.alert_class().includes(tags)) {
                    alert.alert_class(alert.alert_class() + ' ' + tags);
                }
                alert.restartTimer();
            }

            // Scroll to top of page to see alert
            document.body.scrollTop = document.documentElement.scrollTop = 0;
        };
        return self;
    };

    const removeAlertTimerFunc = function (alertObj) {
        return () => {
            viewModel.removeAlert(alertObj);
        };
    };

    const viewModel = ViewModel();

    $(function () {
        // remove closed alerts from backend model
        $(document).on('close.bs.alert','.message-alert', function () {
            viewModel.removeAlert(ko.dataFor(this));
        });

        var message_element = $("#message-alerts").get(0);
        // this element is not available on templates like iframe_domain_login.html
        if (message_element) {
            ko.cleanNode(message_element);
            $(message_element).koApplyBindings(viewModel);
        }
    });

    return {
        alert_user: viewModel.alert_user,
    };
});
