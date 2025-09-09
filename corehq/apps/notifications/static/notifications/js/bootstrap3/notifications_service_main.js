/**
 * Document ready handling for pages that use notifications/js/notifications_service.js
 */

import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import notificationsService from "notifications/js/bootstrap3/notifications_service";
import googleAnalytics from "analytix/js/google";

var initNotifications = function () {
    var csrfToken = $("#csrfTokenContainer").val();
    notificationsService.setRMI(initialPageData.reverse('notifications_service'), csrfToken);
    notificationsService.initService('#js-settingsmenu-notifications');
    notificationsService.relativelyPositionUINotify('.alert-ui-notify-relative');
    notificationsService.initUINotify('.alert-ui-notify');

    $(document).on('click', '.notification-link', function () {
        googleAnalytics.track.event('Notification', 'Opened Message', this.href);
    });
    googleAnalytics.track.click($('#notification-icon'), 'Notification', 'Clicked Bell Icon');
};
$(document).ready(initNotifications);
export default {
    'initNotifications': initNotifications,
};
