hqDefine('hqwebapp/js/mobile_experience_warning', function() {
    $(function() {
        var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
            url = initialPageData.reverse('send_mobile_reminder'),
            $modal = $("#mobile-experience-modal"),
            $videoModal = $("#mobile-experience-video-modal"),
            kissmetrix = hqImport('analytix/js/kissmetrix');
        $modal.modal('show');

        var sendReminder = function (e) {
            $.ajax({
                dataType: 'json',
                url: url,
                type: 'post',
            });
            e.preventDefault();
            $modal.modal('toggle');
            $videoModal.modal();
            kissmetrix.track.event('Clicked mobile experience reminder');
        };

        $.cookie(initialPageData.get('mobile_ux_cookie_name'), true);

        $("#send-mobile-reminder-button").click(sendReminder);
        kissmetrix.track.event('Saw mobile experience warning');
    });

});
