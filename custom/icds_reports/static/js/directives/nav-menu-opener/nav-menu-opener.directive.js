
function NavMenuOpenerController($scope) {
    $scope.openNavMenu = function (event) {
        // todo: this is better implemented with angular events rather
        // than magic div ID names...
        //preventing the click event that opens nav menu from bubbling up the DOM (if bubbled up closeMenu gets triggered)
        event.stopPropagation();
        document.getElementById('nav-menu').style.left = '0';
    };
}

NavMenuOpenerController.$inject = ['$scope'];

window.angular.module('icdsApp').component("navMenuOpener", {
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('nav-menu-opener.directive');
    }],
    controller: NavMenuOpenerController,
});
