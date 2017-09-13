/* globals hqDefine */
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
function(
    $,
    ko
) {
    var message_alert = function(message, tags) {
        var alert_obj = {
            "message": ko.observable(message),
            "alert_class": ko.observable(
                "alert fade in alert-block alert-full page-level-alert message-alert"
            ),
        };
        if (tags) {
            alert_obj.alert_class(alert_obj.alert_class() + " " + tags);
        }
        return alert_obj;
    };
    var message_alerts = ko.observableArray();

    var alert_user = function(message, emphasis, append) {
        var tags = "alert-" + emphasis;
        if (!append || message_alerts().length === 0) {
            message_alerts.push(message_alert(message, tags));
        } else {
            var alert = message_alerts()[0];
            alert.message(alert.message() + "<br>" + message);
            if (!alert.alert_class().includes(tags)) {
                alert.alert_class(alert.alert_class() + ' ' + tags);
            }
        }
    };

    $(function() {
        // remove closed alerts from backend model
        $(document).on('close.bs.alert','.message-alert', function() {
            message_alerts.remove(ko.dataFor(this));
        });

        var message_element = $("#message-alerts").get(0);
        ko.cleanNode(message_element);
        $(message_element).koApplyBindings({
            alerts: message_alerts,
        });
    });

    return {
        alert_user: alert_user,
    };
});
