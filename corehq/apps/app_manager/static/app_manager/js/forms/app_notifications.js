hqDefine("app_manager/js/forms/app_notifications", [
    "moment",
    "hqwebapp/js/bootstrap3/alert_user",
], function (
    moment,
    alertUser,
) {
    var getMessage = function (redisMessage, userId) {
        var msgObj = JSON.parse(redisMessage);
        // only show notifications from other users
        if (msgObj.user_id !== userId) {
            return moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text;
        }
        return "";
    };

    var alertUser = function (userId, callback, context) {
        if (!callback) {
            callback = alertUser.alert_user;
        }
        return function (redisMessage) {
            var message = getMessage(redisMessage, userId);
            if (message) {
                callback.apply(context, [message, 'info', true]);
            }
        };
    };

    return {
        alertUser: alertUser,
    };
});
