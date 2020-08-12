function SortableKpiController() {
    this.toggleCardExpansion = function (cardNumber) {
        // expand/collapse card
        this.expandedCard = (this.expandedCard === cardNumber) ? null : cardNumber;
    };
}

SortableKpiController.$inject = [];

window.angular.module('icdsApp').directive("sortableKpi", ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
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
