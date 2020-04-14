var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').directive("reassignmentMessage", function () {
    return {
        restrict: 'E',
        scope: {
            selectedLocation: '='
        },
        templateUrl: url('icds-ng-template', 'reassignment-message'),
    };
});
