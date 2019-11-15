/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ProgramSummaryController($scope, $http, $log, $routeParams, $location, storageService, userLocationId, haveAccessToAllLocations, isAlertActive) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.filters = ['gender', 'age'];
    vm.step = $routeParams.step;
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];
    vm.isAlertActive = isAlertActive;

    vm.prevDay = moment().subtract(1, 'days').format('Do MMMM, YYYY');
    vm.currentMonth = moment().format("MMMM");
    vm.lastDayOfPreviousMonth = moment().set('date', 1).subtract(1, 'days').format('Do MMMM, YYYY');

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();

    vm.getDataForStep = function (step) {
        var getUrl = url('program_summary', step);
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data.records;
            },
            function (error) {
                $log.error(error);
            }
        );
    };

    vm.steps = {
        "maternal_child": {"route": "/program_summary/maternal_child", "label": "Maternal and Child Nutrition", "data": null},
        "icds_cas_reach": {"route": "/program_summary/icds_cas_reach", "label": "ICDS-CAS Reach", "data": null},
        "demographics": {"route": "/program_summary/demographics", "label": "Demographics", "data": null},
        "awc_infrastructure": {"route": "/program_summary/awc_infrastructure", "label": "AWC Infrastructure", "data": null},
    };

    vm.getDataForStep(vm.step);
}

ProgramSummaryController.$inject = ['$scope', '$http', '$log', '$routeParams', '$location', 'storageService', 'userLocationId', 'haveAccessToAllLocations', 'isAlertActive'];

window.angular.module('icdsApp').directive('programSummaryMobile', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template-mobile', 'program-summary.directive'),
        bindToController: true,
        controller: ProgramSummaryController,
        controllerAs: '$ctrl',
    };
});
