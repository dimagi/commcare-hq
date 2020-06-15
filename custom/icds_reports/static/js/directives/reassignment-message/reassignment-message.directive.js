window.angular.module('icdsApp').directive("reassignmentMessage", ['templateProviderService', function (templateProviderService) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
            selectedLocation: '=',
            selectedDate: '=',
        },
        templateUrl: function () {
            return templateProviderService.getTemplate('reassignment-message');
        },
    };
}]);
