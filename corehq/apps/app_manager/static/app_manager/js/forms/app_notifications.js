/* globals hqDefine moment */
hqDefine('app_manager/js/forms/app_notifications.js', function () {
    function NotifyFunction(userId) {
        return function(msg) {
            var msgObj = JSON.parse(msg);
            // only show notifcations from other users
            if (msgObj.user_id !== userId) {
                var message = moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text;
                hqImport("style/js/alert_user.js").alert_user(message, 'info', true);
            }
        };
    }
    return {NotifyFunction: NotifyFunction};
});
