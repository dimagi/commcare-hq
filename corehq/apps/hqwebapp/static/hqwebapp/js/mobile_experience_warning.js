hqDefine('hqwebapp/js/mobile_experience_warning', function() {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data").get,
        cookieName = "has-seen-mobile-experience-warning";

    if (initialPageData("is_mobile_experience") && !$.cookie(cookieName)) {
        $(function() {
            var toggles = hqImport('hqwebapp/js/toggles');
            if (!toggles.toggleEnabled('MOBILE_SIGNUP_REDIRECT_AB_TEST_CONTROLLER') ||
                    !toggles.toggleEnabled('MOBILE_SIGNUP_REDIRECT_AB_TEST')) {
                return;
            }
            $.cookie(cookieName, true);

            var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
                url = initialPageData.reverse('send_mobile_reminder'),
                $modal = $("#mobile-experience-modal"),
                $videoModal = $("#mobile-experience-video-modal"),
                kissmetrix = hqImport('analytix/js/kissmetrix');

            var sendReminder = function() {
                $.ajax({
                    dataType: 'json',
                    url: url,
                    type: 'post',
                });
                $modal.modal('toggle');
                $videoModal.modal();
                kissmetrix.track.event('Clicked mobile experience reminder');
            };

            $("#send-mobile-reminder-button").click(sendReminder);
            $modal.modal();
            kissmetrix.track.event('Saw mobile experience warning');
        });
    }

});
