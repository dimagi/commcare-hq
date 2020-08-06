window.angular.module('icdsApp').component("reassignmentMessage", {
    bindings: {
        selectedLocation: '<',
        selectedDate: '<',
    },
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('reassignment-message');
    }],
});
