/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ChildrenInitiatedController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Children initiated appropriate complementary feeding";
    vm.steps = {
        'map': {route: '/children_initiated/map', label: 'Map View'},
        'chart': {route: '/children_initiated/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: 'Percentage of children between 6 - 8 months given timely introduction to solid, semi-solid or soft food.',
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
                key: 'Total number of children between age 6 - 8 months' + chosenFilters + ': ',
                value: total,
            },
            {
                key: 'Total number of children (6-8 months) given timely introduction to sold or semi-solid food in the given month' + chosenFilters + ': ',
                value: children,
            },
            {
                key: '% children (6-8 months) given timely introduction to solid or semi-solid food in the given month' + chosenFilters + ': ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getChildrenInitiatedData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of children between 6 - 8 months given timely introduction to solid, semi-solid or soft food. \n' +
        '\n' +
        'Timely intiation of complementary feeding in addition to breastmilk at 6 months of age is a key feeding practice to reduce malnutrition'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of children between age 6 - 8 months: ',
                value: dataInMonth.all,
            },
            {
                key: 'Total number of children (6-8 months) given timely introduction to sold or semi-solid food in the given month: ',
                value: dataInMonth.in_month,
            },
            {
                key: '% children (6-8 months) given timely introduction to solid or semi-solid food in the given month: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

ChildrenInitiatedController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'maternalChildService',
    'locationsService',
    'userLocationId',
    'storageService',
    'genders',
    'baseControllersService',
];

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
