window.angular.module('icdsApp').component('accessDenied', {
    templateUrl: function () {
        var url = hqImport('hqwebapp/js/initial_page_data').reverse;
        return url('icds-ng-template', 'access-denied.directive');
    }
});
