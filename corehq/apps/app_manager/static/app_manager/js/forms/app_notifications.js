"use strict";
/* globals moment */
hqDefine('app_manager/js/forms/app_notifications', function () {
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
            callback = hqImport("hqwebapp/js/bootstrap3/alert_user").alert_user;
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
