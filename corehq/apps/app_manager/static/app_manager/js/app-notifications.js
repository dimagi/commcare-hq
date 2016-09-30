/* globals hqDefine moment */
hqDefine('app_manager/js/app-notifications.js', function () {
    function NotifyFunction(userId, $element) {
        return function(msg) {
            // show a notification when the form has been edited
            var msgObj = JSON.parse(msg);
            if (msgObj.user_id != userId) {
                if ($element.hasClass('hidden')) {
                    var dismissButton = '<button type="button" class="close" data-dismiss="alert">&times;</button>';
                    $element.removeClass('hidden').html(dismissButton);
                }
                $element.append(moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text + '<br>');
            }
        };

    };
    return {NotifyFunction: NotifyFunction};
});
