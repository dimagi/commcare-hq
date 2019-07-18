/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdhaarController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
    userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "Percent Aadhaar-seeded Beneficiaries";
    vm.steps = {
        'map': {route: '/demographics/adhaar/map', label: 'Map View'},
        'chart': {route: '/demographics/adhaar/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage beneficiary',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification has been captured. ',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = demographicsService.getAdhaarData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification has been captured. ',
    };
    vm.chartOptions = vm.getChartOptions(options);

    vm.tooltipContent = function(monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: $filter('indiaNumbers')(day.in_month),
            },
            {
                indicator_name: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: d3.format('.2%')(day.y),
            }]
        );
    };
}

AdhaarController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

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
