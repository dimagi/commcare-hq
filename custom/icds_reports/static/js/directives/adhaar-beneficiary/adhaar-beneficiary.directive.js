/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdhaarController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
    dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
    baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "Aadhaar-seeded Beneficiaries";
    vm.serviceDataFunction = demographicsService.getAdhaarData;
    vm.steps = vm.getSteps('/demographics/adhaar/');
    vm.data = {
        legendTitle: 'Percentage beneficiary',
    };
    vm.filters = ['age', 'gender', 'data_period'];
    vm.rightLegend = {
        info: 'Of the total number of ICDS beneficiaries, the percentage whose Aadhaar identification has been captured. ',
    };

    vm.getPopupData = function (row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return [
            {
                indicator_name: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total number of ICDS beneficiaries, the percentage whose Aadhaar identification has been captured. ',
    };
    vm.chartOptions = vm.getChartOptions(options);

    vm.tooltipContent = function (monthName, day) {
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

AdhaarController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'demographicsService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('adhaarBeneficiary', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdhaarController,
        controllerAs: '$ctrl',
    };
}]);
