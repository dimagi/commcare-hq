/* globals hqDefine moment */
hqDefine('app_manager/js/app-notifications.js', function () {
    function NotifyFunction(userId, $element) {
        return function(msg) {
            // show a notification when the form has been edited
            var msgObj = JSON.parse(msg);
            if (msgObj.user_id != userId) {
                var $inner;
                if (!$element.html()) {
                    $inner = $('<div />').addClass('alert alert-info');
                    var dismissButton = '<button type="button" class="close" data-dismiss="alert">&times;</button>';
                    $inner.html(dismissButton);
                    $element.removeClass('hidden').append($inner);
                } else {
                    $inner = $($element.children()[0]);
                }
                console.log('inner', $inner);
                $inner.append(moment(msgObj.timestamp).format('h:mm:ss a') + ': ' + msgObj.text + '<br>');
            }
        };

    };
    return {NotifyFunction: NotifyFunction};
});
