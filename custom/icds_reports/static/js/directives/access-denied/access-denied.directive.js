
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').directive('accessDenied', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'access-denied.directive'),
    };
});
