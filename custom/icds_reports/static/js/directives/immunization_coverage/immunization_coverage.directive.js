/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ImmunizationCoverageController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService, genders,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = maternalChildService.getImmunizationCoverageData;
    vm.haveAccessToFeatures = haveAccessToFeatures;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Immunization coverage (at age 1 year)";
    vm.steps = vm.getSteps('/maternal_and_child/immunization_coverage/');
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age', 'data_period'];
    vm.rightLegend = {
        info : 'Of the total number of children enrolled for Anganwadi Services who are between 1-2 years old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1.<br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1'
    };


    vm.getPopupData = function (row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children = row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';

        return [
            {
                indicator_name: 'Total number of ICDS Child beneficiaries between 1-2 years old' + chosenFilters + ': ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total number of children between 1-2 years old who have received complete immunizations required by age 1' + chosenFilters + ': ',
                indicator_value: children,
            },
            {
                indicator_name: '% of children between 1-2 years old who have received complete immunizations required by age 1' + chosenFilters + ': ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    vm.resetAdditionalFilter = function () {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total number of children enrolled for Anganwadi Services who are between 1-2 years old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1. <br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of ICDS Child beneficiaries between 1-2 years old: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total number of children between 1-2 years old who have received complete immunizations required by age 1: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% of children between 1-2 years old who have received complete immunizations required by age 1: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

ImmunizationCoverageController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'maternalChildService', 'locationsService', 'dateHelperService', 'navigationService',
    'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService',
    'isAlertActive', 'isMobile', 'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('immunizationCoverage', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: ImmunizationCoverageController,
        controllerAs: '$ctrl',
    };
}]);
