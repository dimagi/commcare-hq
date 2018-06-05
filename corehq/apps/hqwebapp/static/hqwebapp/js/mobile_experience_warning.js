hqDefine('hqwebapp/js/mobile_experience_warning', function() {
    $(function() {
        var cookieName = "has-seen-mobile-experience-warning";

        if (!$.cookie(cookieName)) {
            $.cookie(cookieName, true);

            $('.full-screen-no-background-modal').css('width', $(window).innerWidth() + 'px');

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
        }
    });

});
