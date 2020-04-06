/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EarlyInitiationBreastfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService, genders,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        false, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = maternalChildService.earlyInitiationBreastfeeding;

    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Early Initiation of Breastfeeding";
    vm.steps = vm.getSteps('/maternal_and_child/early_initiation/');
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.filters = ['age'];

    vm.rightLegend = {
        info: 'Of the children born in the given month and enrolled for Anganwadi services, the percentage whose breastfeeding was initiated within 1 hour of delivery.\n' +
        '\n' +
        'Early initiation of breastfeeding ensure the newborn recieves the "first milk" rich in nutrients and encourages exclusive breastfeeding practice',
    };

    vm.getPopupData = function (row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var birth = row ? $filter('indiaNumbers')(row.birth) : 'N/A';
        var percent = row ? d3.format('.2%')(row.birth / (row.in_month || 1)) : 'N/A';
        return [
            {
                indicator_name: 'Total Number of Children born in the current month' + chosenFilters + ': ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total Number of Children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                indicator_value: birth,
            },
            {
                indicator_name: '% children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the children born in the given month and enrolled for Anganwadi services, the percentage whose breastfeeding was initiated within 1 hour of delivery. \n' +
        '\n' +
        'Early initiation of breastfeeding ensure the newborn recieves the "first milk" rich in nutrients and encourages exclusive breastfeeding practice',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total Number of Children born in the given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total Number of Children who were put to the breast within one hour of birth: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.birth),
            },
            {
                indicator_name: '% children who were put to the breast within one hour of birth: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };

    vm.resetAdditionalFilter = function () {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

EarlyInitiationBreastfeedingController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'maternalChildService', 'locationsService', 'dateHelperService', 'navigationService',
    'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService',
    'isAlertActive', 'isMobile',
];

window.angular.module('icdsApp').directive('earlyInitiationBreastfeeding', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EarlyInitiationBreastfeedingController,
        controllerAs: '$ctrl',
    };
}]);
