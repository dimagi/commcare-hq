var url = hqImport('hqwebapp/js/urllib').reverse;

function DotLinkController($location) {
    var vm = this;

    vm.isActive = function() {
        return $location.path() === vm.route;
    };

    vm.onClick = function() {
        $location.path(vm.route);
    };
}

DotLinkController.$inject = ['$location'];

window.angular.module('icdsApp').directive('dotLink', function() {
    return {
        restrict: 'E',
        scope: {
            route: '@',
            label: '@',
        },
        templateUrl: url('icds-ng-template', 'dot-link.directive'),
        bindToController: true,
        controller: DotLinkController,
        controllerAs: '$ctrl',
    };
});
