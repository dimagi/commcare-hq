/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdhaarController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
    userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Percent Aadhaar-seeded Beneficiaries";
    vm.steps = {
        'map': {route: '/adhaar/map', label: 'Map View'},
        'chart': {route: '/adhaar/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage beneficiary',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Percentage of individuals registered using CAS whose Aadhaar identification has been captured',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                value: inMonth,
            },
            {
                key: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function() {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getAdhaarData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage number of ICDS beneficiaries whose Aadhaar identification has been captured'
    );

    vm.getTooltipContent = function(monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                value: $filter('indiaNumbers')(day.in_month),
            },
            {
                key: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                value: d3.format('.2%')(day.y),
            }]
        );
    };
}

AdhaarController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'demographicsService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('adhaarBeneficiary', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdhaarController,
        controllerAs: '$ctrl',
    };
});
