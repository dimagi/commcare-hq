window.angular.module('icdsApp').directive("reassignmentMessage", function () {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
            selectedLocation: '=',
            selectedDate: '=',
        },
        templateUrl: url('icds-ng-template', 'reassignment-message'),
    };
});
