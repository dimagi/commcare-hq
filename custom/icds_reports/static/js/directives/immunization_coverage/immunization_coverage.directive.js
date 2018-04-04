/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ImmunizationCoverageController($scope, $routeParams, $location, $filter, maternalChildService,
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

    vm.label = "Immunization coverage (at age 1 year)";
    vm.steps = {
        'map': {route: '/immunization_coverage/map', label: 'Map View'},
        'chart': {route: '/immunization_coverage/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: 'Percentage of children 1 year+ who have received complete immunization as per National Immunization Schedule of India required by age 1.<br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
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
                key: 'Total number of ICDS Child beneficiaries older than 1 year' + chosenFilters + ': ',
                value: total,
            },
            {
                key: 'Total number of children who have recieved complete immunizations required by age 1' + chosenFilters + ': ',
                value: children,
            },
            {
                key: '% of children who have recieved complete immunizations required by age 1' + chosenFilters + ': ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getImmunizationCoverageData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of children 1 year+ who have received complete immunization as per National Immunization Schedule of India required by age 1. <br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/> If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of ICDS Child beneficiaries older than 1 year: ',
                value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                key: 'Total number of children who have recieved complete immunizations required by age 1: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: '% of children who have recieved complete immunizations required by age 1: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

ImmunizationCoverageController.$inject = [
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
