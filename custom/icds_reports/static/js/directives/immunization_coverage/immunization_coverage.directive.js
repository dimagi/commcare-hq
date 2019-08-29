/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ImmunizationCoverageController($scope, $routeParams, $location, $filter, maternalChildService,
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

    vm.label = "Immunization coverage (at age 1 year)";
    vm.steps = {
        'map': {route: '/maternal_and_child/immunization_coverage/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/immunization_coverage/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: 'Of the total number of children enrolled for Anganwadi Services who are over a year old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1.<br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
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
                indicator_name: 'Total number of ICDS Child beneficiaries older than 1 year' + chosenFilters + ': ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total number of children who have recieved complete immunizations required by age 1' + chosenFilters + ': ',
                indicator_value: children,
            },
            {
                indicator_name: '% of children who have recieved complete immunizations required by age 1' + chosenFilters + ': ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getImmunizationCoverageData(vm.step, vm.filtersData).then(
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
        'captionContent': ' Of the total number of children enrolled for Anganwadi Services who are over a year old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1. <br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of ICDS Child beneficiaries older than 1 year: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total number of children who have recieved complete immunizations required by age 1: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% of children who have recieved complete immunizations required by age 1: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

ImmunizationCoverageController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('immunizationCoverage', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: ImmunizationCoverageController,
        controllerAs: '$ctrl',
    };
});
