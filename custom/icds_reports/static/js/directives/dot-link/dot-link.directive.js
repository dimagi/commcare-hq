var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function DotLinkController($location) {
    var vm = this;

    vm.isActive = function () {
        return $location.path() === vm.route;
    };

    vm.onClick = function () {
        $location.path(vm.route);
    };
}

DotLinkController.$inject = ['$location'];

window.angular.module('icdsApp').directive('dotLink', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        scope: {
            id: '@',
            route: '@',
            label: '@',
            image: '@',
        },
        templateUrl: function () {
            return templateProviderService.getTemplate('dot-link.directive');
        },
        bindToController: true,
        controller: DotLinkController,
        controllerAs: '$ctrl',
    };
}]);
