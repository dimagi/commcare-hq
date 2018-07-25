var google = hqImport('analytix/js/google');

window.angular.module('icdsApp').factory('gaService', [function() {
    return {
        trackCategory: google.trackCategory,
        trackEvent: google.track.event,
        trackClick: google.track.click,
    };
}]);
