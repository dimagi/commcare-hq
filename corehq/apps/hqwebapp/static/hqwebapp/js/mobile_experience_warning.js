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
            url = initialPageData.reverse('send_desktop_reminder'),
            $modal = $("#mobile-experience-modal"),
            $videoModal = $("#mobile-experience-video-modal");

        var sendReminder = function() {
            $.ajax({
                dataType: 'json',
                url: url,
                type: 'post',
            });
            $modal.modal('toggle');
            $videoModal.modal();
        };

        $("#send-mobile-reminder-button").click(sendReminder);
        $modal.modal();
    });
});
