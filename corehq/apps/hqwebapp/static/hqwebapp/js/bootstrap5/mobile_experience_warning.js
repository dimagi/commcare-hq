
hqDefine('hqwebapp/js/bootstrap5/mobile_experience_warning', [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "analytix/js/kissmetrix",
    "es6!hqwebapp/js/bootstrap5_loader",
    "jquery.cookie/jquery.cookie",
], function (
    $,
    initialPageData,
    kissmetrix,
    bootstrap,
) {
    $(function () {

        if (initialPageData.get('show_mobile_ux_warning')) {
            let reminderUrl = initialPageData.reverse('send_mobile_reminder'),
                uxWarningModalElement = document.getElementById('mobile-experience-modal'),
                videoModalElement = document.getElementById('mobile-experience-video-modal'),
                uxWarningModal = new bootstrap.Modal(uxWarningModalElement);

            uxWarningModal.show();
            let setCookie = function () {
                $.cookie(initialPageData.get('mobile_ux_cookie_name'), true, {
                    path: '/',
                    secure: initialPageData.get('secure_cookies'),
                });
            };
            uxWarningModalElement.addEventListener('hidden.bs.modal', function () {
                setCookie();
            });
            videoModalElement.addEventListener('shown.bs.modal', function () {
                uxWarningModal.hide();
            });

            let sendReminder = function (e) {
                $.ajax({
                    dataType: 'json',
                    url: reminderUrl,
                    type: 'post',
                });
                let videoModal = new bootstrap.Modal(videoModalElement);
                videoModal.show();
                kissmetrix.track.event('Clicked mobile experience reminder');
            };

            $("#send-mobile-reminder-button").click(sendReminder);
            kissmetrix.track.event('Saw mobile experience warning');
        }

    });
});
