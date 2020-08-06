

function HelpPopupController($scope) {
    // used by mobile dashboard only
    $scope.activeInfoHeading = '';
    $scope.activeInfoHelp = '';
    function showHelp(heading, help) {
        $scope.activeInfoHeading = heading;
        $scope.activeInfoHelp = help;
        document.getElementById('summary-info').style.height = '90vh';
        document.getElementById('summary-info').style.top = '10vh';
        document.getElementById('summary-info').style.paddingTop = '30px';
    }
    function hideHelp() {
        document.getElementById('summary-info').style.height = '0';
        document.getElementById('summary-info').style.top = '100vh';
        document.getElementById('summary-info').style.paddingTop = '0px';
    }
    $scope.hideHelp = hideHelp;
    $scope.$on('showHelp', function (event, heading, help) {
        showHelp(heading, help);
    });
}

HelpPopupController.$inject = ['$scope'];

window.angular.module('icdsApp').component("helpPopup", {
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('help-popup.directive');
    }],
    controller: HelpPopupController,
});
