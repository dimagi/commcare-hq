function FiltersController(userLocationId) {
    this.data.location_id = userLocationId;
}

FiltersController.$inject = ['userLocationId'];

window.angular.module('icdsApp').directive("filters", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            data: '=',
            filters: '=',
            selectedLocations: '=',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'filters'),
        controller: FiltersController,
        controllerAs: "$ctrl",
    };
});
