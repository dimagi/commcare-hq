hqDefine('hqwebapp/js/mobile_experience_warning', function() {
    if (window.innerWidth > 800 && window.innerHeight > 600) {
        return;
    }

    var cookieName = "has-seen-mobile-experience-warning";
    if ($.cookie(cookieName)) {
        return;
    }

    $(function() {
        var toggles = hqImport('hqwebapp/js/toggles');
        if (!toggles.toggleEnabled('MOBILE_SIGNUP_REDIRECT_AB_TEST_CONTROLLER') ||
                !toggles.toggleEnabled('MOBILE_SIGNUP_REDIRECT_AB_TEST')) {
            return;
        }
        $.cookie(cookieName, true);

        var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
            alertUser = hqImport('hqwebapp/js/alert_user'),
            url = initialPageData.reverse('send_desktop_reminder');

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
        $("#mobile-experience-modal").modal();
    });
});
