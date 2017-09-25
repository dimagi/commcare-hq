/* globals hqDefine moment */
hqDefine('app_manager/js/forms/app_notifications', function () {
    var getMessage = function(redisMessage, userId) {
        var msgObj = JSON.parse(redisMessage);
        // only show notifications from other users
console.log("in getMessage, ids = " + msgObj.user_id + ", " + userId);
debugger;
        //if (msgObj.user_id !== userId) {
            return moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text;
        //}
        return "";
    };

    var alertUser = function(callback) {
console.log("calling alertUser, callback=" + callback);
debugger;
        if (!callback) {
            callback = hqImport("hqwebapp/js/alert_user").alert_user;
        }
        return function(userId) {
console.log("calling inner function, userId=" + userId);
debugger;
            return function(redisMessage) {
console.log("calling innermost function, redisMessage=" + redisMessage);
debugger;
                var message = getMessage(redisMessage, userId);
console.log("message=" + message);
debugger;
                if (message) {
                    callback(message, 'info', true);
                }
            };
        };
    };

    return {
        alertUser: alertUser,
    };
});
