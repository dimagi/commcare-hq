/* globals hqDefine moment */
hqDefine('app_manager/js/forms/app_notifications', function () {
    var getMessage = function(redisMessage, userId) {
        var msgObj = JSON.parse(redisMessage);
        // only show notifications from other users
        if (msgObj.user_id !== userId) {
            return moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text;
        }
        return "";
    };

    var alertUser = function(alertCallback) {
        return function(userId) {
            return function(redisMessage) {
                var message = getMessage(redisMessage, userId);
                if (message) {
                    callback(message, 'info', true);
                }
            };
        };
    };

    var alertUserHQ = alertUser(hqImport("hqwebapp/js/alert_user").alert_user);
    var alertUserFormBuilder = alertUser($("#formdesigner").vellum("get").alertUser);

    return {
        alertUser: alertUserHQ,
        alertUserFormBuilder: alertUserFormBuilder,
    };
});
