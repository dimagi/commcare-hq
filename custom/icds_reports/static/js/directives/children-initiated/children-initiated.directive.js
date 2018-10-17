/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ChildrenInitiatedController($scope, $routeParams, $location, $filter, maternalChildService,
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

    vm.label = "Children initiated appropriate complementary feeding";
    vm.steps = {
        'map': {route: '/maternal_and_child/children_initiated/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/children_initiated/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: 'Of the total children enrolled for Anganwadi services between the ages of 6 to 8 months, the percentage that was given a timely introduction to solid, semi-solid or soft food.\n' +
        '\n' +
        'Timely intiation of complementary feeding in addition to breastmilk at 6 months of age is a key feeding practice to reduce malnutrition',
    };

    vm.templatePopup = function(loc, row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children = row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of children between age 6 - 8 months' + chosenFilters + ': ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total number of children (6-8 months) given timely introduction to sold or semi-solid food in the given month' + chosenFilters + ': ',
                indicator_value: children,
            },
            {
                indicator_name: '% children (6-8 months) given timely introduction to solid or semi-solid food in the given month' + chosenFilters + ': ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getChildrenInitiatedData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total children enrolled for Anganwadi services between the ages of 6 to 8 months, the percentage that was given a timely introduction to solid, semi-solid or soft food.\n' +
        '\n' +
        'Timely intiation of complementary feeding in addition to breastmilk at 6 months of age is a key feeding practice to reduce malnutrition',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of children between age 6 - 8 months: ',
                indicator_value: dataInMonth.all,
            },
            {
                indicator_name: 'Total number of children (6-8 months) given timely introduction to sold or semi-solid food in the given month: ',
                indicator_value: dataInMonth.in_month,
            },
            {
                indicator_name: '% children (6-8 months) given timely introduction to solid or semi-solid food in the given month: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

ChildrenInitiatedController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('childrenInitiated', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: ChildrenInitiatedController,
        controllerAs: '$ctrl',
    };
});
