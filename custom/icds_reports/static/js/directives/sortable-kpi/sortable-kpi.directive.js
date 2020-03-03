var url = hqImport('hqwebapp/js/initial_page_data').reverse;


function SortableKpiController($rootScope, $scope) {
    this.expandedCard = -1;
    this.toggleCardExpansion = function (cardNumber) {
        // expand/collapse card
        this.expandedCard = (this.expandedCard === cardNumber) ? -1 : cardNumber;
    }
}

SortableKpiController.$inject = ['$rootScope', '$scope'];

window.angular.module('icdsApp').directive("sortableKpi", ['templateProviderService', function (templateProviderService) {
    return {
        restrict:'E',
        scope: {
            data: '=',
        },
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('sortable-kpi.directive');
        },
        controller: SortableKpiController,
        controllerAs: "$ctrl",
    };
}]);
