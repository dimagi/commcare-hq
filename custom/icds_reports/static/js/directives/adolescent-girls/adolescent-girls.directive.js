/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdolescentWomenController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
    dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
    baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile, haveAccessToFeatures);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "Adolescent Girls (11-14 years)";
    vm.serviceDataFunction = demographicsService.getAdolescentGirlsData;
    vm.usePercentage = false;
    vm.steps = vm.getSteps('/demographics/adolescent_girls/');
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['age', 'gender'];


    vm.rightLegend = {
        info: 'Of the total number of adolescent girls (aged 11-14 years),the percentage of adolescent girls who are out of school',
    };



    vm.getPopupData = function (row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";

        var data = [
            {
                indicator_name: 'Number of adolescent girls (11-14 years) who are out of school: ',
                indicator_value: valid,
            },
            {
                indicator_name: 'Total Number of adolescent girls (11-14 years) who are registered: ',
                indicator_value: all,
            },
            {
                indicator_name: 'Percentage of adolescent girls (11-14 years) who are out of school: ',
                indicator_value: percent,
            },
        ];


        return data;
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ",",
        'captionContent': 'Of the total number of adolescent girls (aged 11-14 years),the percentage of adolescent girls who are out of school',
    };

    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getDisableIndex = function () {
        var i = -1;
        if (!haveAccessToAllLocations) {
            window.angular.forEach(vm.selectedLocations, function (key, value) {
                if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                    i = value;
                }
            });
        }
        return i;
    };

    vm.tooltipContent = function (monthName, day) {
        var tooltipdata;

        tooltipdata = [{
            indicator_name: 'Number of adolescent girls (11-14 years) who are out of school: ',
            indicator_value: $filter('indiaNumbers')(day.y),
        },
        {
            indicator_name: 'Total Number of adolescent girls (11-14 years) who are registered: ',
            indicator_value: $filter('indiaNumbers')(day.all),
        },
        {
            indicator_name: 'Percentage of adolescent girls (11-14 years) who are out of school: ',
            indicator_value: d3.format('.2%')(day.y / (day.all || 1)),
        }];


        return vm.createTooltipContent(
            monthName,
            tooltipdata
        );
    };
}

AdolescentWomenController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'demographicsService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile','haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('adolescentGirls', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdolescentWomenController,
        controllerAs: '$ctrl',
    };
}]);
