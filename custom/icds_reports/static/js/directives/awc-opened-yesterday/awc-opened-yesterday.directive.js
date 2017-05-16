var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').directive('awcOpenedYesterday', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-opened-yesterday.directive'),
        bindToController: true,
        controller: function() {
            this.step = 'map';
            this.mapData = {};
        },
        controllerAs: '$ctrl',
    };
});
