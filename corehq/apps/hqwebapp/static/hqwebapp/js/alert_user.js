/*
    This is the knockout-based, javascript analog of messages in Django.

    Use the function `alert_user` to make a message appear on the page.
    This accepts three args, message, emphasis and append.
    Emphasis corresponds to bootstrap styling, and can be
    "success", "danger", "info", or "warning".
    If specified, "append" will cause the message to be appended to the existing notification
    bubble (as opposed to making a new bubble).
    NOTE: append will change the class of the alert if it is more severe
    (success < info < warning < danger)

    alert_user("Awesome job!", "success", true);
*/
hqDefine("hqwebapp/js/alert_user", [
    "jquery",
    "knockout",
    "hqwebapp/js/hq.helpers",
],
function (
    $,
    ko
) {
    var MessageAlert = function (message, tags) {
        var self = {
            "message": ko.observable(message),
            "alert_class": ko.observable(
                "alert fade in message-alert"
            ),
        };
        if (tags) {
            self.alert_class(self.alert_class() + " " + tags);
        }
        return self;
    };

    const ViewModel = function() {
        let self = this;
        self.alerts = ko.observableArray();
        self.removeAlert = (alertObj) => {
            self.alerts.remove(alertObj);
        };

        self.alert_user = function (message, emphasis, append) {
            var tags = "alert-" + emphasis;
            if (!append || self.alerts().length === 0) {
                self.alerts.push(MessageAlert(message, tags));
            } else {
                var alert = self.alerts()[0];
                alert.message(alert.message() + "<br>" + message);
                if (!alert.alert_class().includes(tags)) {
                    alert.alert_class(alert.alert_class() + ' ' + tags);
                }
            }

            // Scroll to top of page to see alert
            document.body.scrollTop = document.documentElement.scrollTop = 0;
        };
        return self;
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
