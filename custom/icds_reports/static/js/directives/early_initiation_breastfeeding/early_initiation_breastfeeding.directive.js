/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EarlyInitiationBreastfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Early Initiation of Breastfeeding";
    vm.steps = {
        'map': {route: '/maternal_and_child/early_initiation/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/early_initiation/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.filters = ['age'];

    vm.rightLegend = {
        info: 'Of the children born in the last month and enrolled for Anganwadi services, the percentage whose breastfeeding was initiated within 1 hour of delivery.\n' +
        '\n' +
        'Early initiation of breastfeeding ensure the newborn recieves the "first milk" rich in nutrients and encourages exclusive breastfeeding practice',
    };

    vm.templatePopup = function(loc, row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var birth = row ? $filter('indiaNumbers')(row.birth) : 'N/A';
        var percent = row ? d3.format('.2%')(row.birth / (row.in_month || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total Number of Children born in the given month' + chosenFilters + ': ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total Number of Children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                indicator_value: birth,
            },
            {
                indicator_name: '% children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.earlyInitiationBreastfeeding(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the children born in the last month and enrolled for Anganwadi services, the percentage whose breastfeeding was initiated within 1 hour of delivery. \n' +
        '\n' +
        'Early initiation of breastfeeding ensure the newborn recieves the "first milk" rich in nutrients and encourages exclusive breastfeeding practice',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = 1100;
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

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

EarlyInitiationBreastfeedingController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('earlyInitiationBreastfeeding', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EarlyInitiationBreastfeedingController,
        controllerAs: '$ctrl',
    };
});
