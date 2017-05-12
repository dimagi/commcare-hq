
var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').directive('underweightChildrenReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'underweight-children-report.directive'),
        bindToController: true,
        controller: function() {},
        controllerAs: '$ctrl',
    };
});
