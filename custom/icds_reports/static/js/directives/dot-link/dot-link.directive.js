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

window.angular.module('icdsApp').component('dotLink', {
    bindings: {
        id: '@',
        route: '@',
        label: '@',
        image: '@',
    },
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('dot-link.directive');
    }],
    controller: DotLinkController,
    controllerAs: '$ctrl',
});
