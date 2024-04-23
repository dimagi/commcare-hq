'use strict';
hqDefine('hqwebapp/js/mobile_experience_warning', [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "analytix/js/kissmetrix",
    "jquery.cookie/jquery.cookie",
], function (
    $,
    initialPageData,
    kissmetrix
) {
    $(function () {

        if (initialPageData.get('show_mobile_ux_warning')) {
            var reminderUrl = initialPageData.reverse('send_mobile_reminder'),
                $modal = $("#mobile-experience-modal"),
                $videoModal = $("#mobile-experience-video-modal");

            var setCookie = function () {
                $.cookie(initialPageData.get('mobile_ux_cookie_name'), true, {
                    path: '/',
                    secure: initialPageData.get('secure_cookies'),
                });
            };

            $modal.find('.close').click(function (e) {
                e.preventDefault();
                $modal.removeClass('modal-force-show');
                setCookie();
            });

            var sendReminder = function (e) {
                $.ajax({
                    dataType: 'json',
                    url: reminderUrl,
                    type: 'post',
                });
                e.preventDefault();
                $videoModal.modal();
                $videoModal.on('shown.bs.modal', function () {
                    $modal.removeClass('modal-force-show');
                });
                kissmetrix.track.event('Clicked mobile experience reminder');
                setCookie();
            };

            $("#send-mobile-reminder-button").click(sendReminder);
            kissmetrix.track.event('Saw mobile experience warning');
        }

    });
});
