var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MobileDotLinkController($location) {
    var vm = this;

    vm.isActive = function() {
        return $location.path() === vm.route;
    };

    vm.onClick = function() {
        $location.path(vm.route);
    };
}

MobileDotLinkController.$inject = ['$location'];

window.angular.module('icdsApp').directive('mobileDotLink', function() {
    return {
        restrict: 'E',
        scope: {
            id: '@',
            route: '@',
            label: '@',
            image: '@',
        },
        templateUrl: url('icds-ng-template', 'mobile-dot-link.directive'),
        bindToController: true,
        controller: MobileDotLinkController,
        controllerAs: '$ctrl',
    };
});
