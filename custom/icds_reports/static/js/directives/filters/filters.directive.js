function FiltersController() {
}

window.angular.module('icdsApp').directive("filters", function () {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
            data: '=',
            filters: '=',
            selectedLocations: '=',
            isOpenModal: '=?',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'filters'),
        controller: FiltersController,
        controllerAs: "$ctrl",
    };
});
