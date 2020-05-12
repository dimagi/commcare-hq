/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EnrolledChildrenController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService, genders, ages,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = demographicsService.getEnrolledChildrenData;
    vm.usePercentage = false;
    vm.forceYAxisFromZero = true;


    var ageIndex = _.findIndex(ages, function (x) {
        return x.id === vm.filtersData.age;
    });
    if (ageIndex !== -1) {
        vm.ageLabel = ages[ageIndex].name;
    }

    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Children enrolled for Anganwadi Services";
    vm.steps = vm.getSteps('/demographics/enrolled_children/');
    vm.data = {
        legendTitle: 'Number of Children',
    };
    if (vm.step === 'chart') {
        vm.filters = ['age'];
    } else {
        vm.filters = [];
    }

    vm.rightLegend = {
        info: 'Of the total number of children between 0-6 years, the percentage of children who are enrolled for Anganwadi Services',
    };
    vm.hideRanking = true;

    vm.getPopupData = function (row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '0 - 6 years';
        var delimiter = gender && age ? ', ' : '';
        var chosenFilters = gender || age ? '(' + gender + delimiter + age + ')' : '';
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return [
            {
                indicator_name: 'Number of children ' + chosenFilters + ' who are enrolled for Anganwadi Services: ',
                indicator_value: valid,
            },
            {
                indicator_name: 'Total number of children ' + chosenFilters + ' who are registered: ',
                indicator_value: all,
            },
            {
                indicator_name: 'Percentage of registered children ' + chosenFilters + ' who are enrolled for Anganwadi Services: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%m/%d/%y',
        'yAxisTickFormat': ",",
        'captionContent': ' Of the total number of children between 0-6 years, the percentage of children who are enrolled for Anganwadi Services',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.type = 'multiBarChart';
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    delete vm.chartOptions.chart.tooltips;
    vm.chartOptions.chart.useInteractiveGuideline = false;
    vm.chartOptions.chart.tooltip = function (key, x) {
        var data = _.find(vm.chartData[0].values, function (num) {
            return num.x === x;
        });
        return vm.tooltipContent(data, x);
    };
    vm.chartOptions.chart.xAxis = {
        axisLabel: '',
        showMaxMin: true,
        tickValues: function () {
            return ["0-1 month", "1-6 months", "6-12 months", "1-3 years", "3-6 years"];
        },
    };
    vm.chartOptions.chart.showControls = false;

    vm.tooltipContent = function (dataInMonth, x) {
        var average = (dataInMonth.all !== 0) ? d3.format(".2%")(dataInMonth.y / dataInMonth.all) : 0;
        return "<div>Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services: <strong>"
            + $filter('indiaNumbers')(dataInMonth.all) + "</strong></div>"
            + "<div>% of children " + x + ": <strong>" + average + "</strong></div>";
    };

    vm.resetAdditionalFilter = function () {
        vm.filtersData.gender = '';
        vm.filtersData.age = '';
        $location.search('gender', null);
        $location.search('age', null);
    };

    vm.resetOnlyAgeAdditionalFilter = function () {
        vm.filtersData.age = '';
        $location.search('age', null);
    };
}

EnrolledChildrenController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'demographicsService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'genders', 'ages', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive',
    'isMobile', 'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('enrolledChildren', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EnrolledChildrenController,
        controllerAs: '$ctrl',
    };
}]);
