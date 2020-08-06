function FiltersController() {
}

window.angular.module('icdsApp').component("filters", {
    bindings: {
        data: '<',
        filters: '<',
        selectedLocations: '<',
        isOpenModal: '<?',
    },
    templateUrl: function () {
        var url = hqImport('hqwebapp/js/initial_page_data').reverse;
        return url('icds-ng-template', 'filters');
    },
    controller: FiltersController,
    controllerAs: "$ctrl",
});
