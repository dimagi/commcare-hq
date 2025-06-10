import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import kissmetrix from "analytix/js/kissmetrix";
import { Modal } from "bootstrap5";
import "jquery.cookie/jquery.cookie";

$(function () {

    if (initialPageData.get('show_mobile_ux_warning')) {
        let reminderUrl = initialPageData.reverse('send_mobile_reminder'),
            uxWarningModalElement = document.getElementById('mobile-experience-modal'),
            videoModalElement = document.getElementById('mobile-experience-video-modal'),
            uxWarningModal = new Modal(uxWarningModalElement);

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
            let videoModal = new Modal(videoModalElement);
            videoModal.show();
            kissmetrix.track.event('Clicked mobile experience reminder');
        };

        $("#send-mobile-reminder-button").click(sendReminder);
        kissmetrix.track.event('Saw mobile experience warning');
    }

});
