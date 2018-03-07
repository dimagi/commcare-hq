hqDefine('hqwebapp/js/mobile_experience_warning', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        alertUser = hqImport('hqwebapp/js/alert_user');

    $(function() {
        var url = initialPageData.reverse('send_desktop_reminder');

        var sendReminder = function() {
            $.ajax({
                dataType: 'json',
                url: url,
                type: 'post',
                success: alertUser.alert_user.bind(this, "The reminder has been sent", "success")
            });
            closeModal();
            showVideo();
        };
        var closeModal = function() {};
        var showVideo = function() {};

        $("#send-mobile-reminder-button").click(sendReminder);
    });
});
