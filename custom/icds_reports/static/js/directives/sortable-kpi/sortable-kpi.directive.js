function SortableKpiController() {
    this.toggleCardExpansion = function (cardNumber) {
        // expand/collapse card
        this.expandedCard = (this.expandedCard === cardNumber) ? null : cardNumber;
    };
}

SortableKpiController.$inject = [];

window.angular.module('icdsApp').component("sortableKpi", {
    bindings: {
        data: '<',
    },
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('sortable-kpi.directive');
    }],
    controller: SortableKpiController,
    controllerAs: "$ctrl",
});
