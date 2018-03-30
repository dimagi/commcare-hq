/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EnrolledChildrenController($scope, $routeParams, $location, $filter, demographicsService,
                                    locationsService, userLocationId, storageService, genders, ages,
                                    baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;

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

    vm.label = "Children (0-6 years) who are enrolled for Anganwadi Services";
    vm.steps = {
        'map': {route: '/enrolled_children/map', label: 'Map View'},
        'chart': {route: '/enrolled_children/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Children',
    };
    if (vm.step === 'chart') {
        vm.filters = ['age'];
    } else {
        vm.filters = [];
    }

    vm.rightLegend = {
        info: 'Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services',
    };
    vm.hideRanking = true;

    vm.templatePopup = function(loc, row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '0 - 6 years';
        var delimiter = gender && age ? ', ' : '';
        var chosenFilters = gender || age ? '(' + gender + delimiter + age + ')' : '';
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Number of children ' + chosenFilters + ' who are enrolled for Anganwadi Services: ',
                value: valid,
            },
            {
                key: 'Total number of children ' + chosenFilters + ' who are registered: ',
                value: all,
            },
            {
                key: 'Percentage of registered children ' + chosenFilters + ' who are enrolled for Anganwadi Services: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getEnrolledChildrenData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(false, true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%m/%d/%y', ",",
        ' Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    delete vm.chartOptions.chart.tooltips;
    vm.chartOptions.chart.useInteractiveGuideline = false;
    vm.chartOptions.chart.tooltip = function (key, x) {
        var data = _.find(vm.chartData[0].values, function(num) { return num.x === x;});
        return vm.getTooltipContent(data, x);
    };
    vm.chartOptions.chart.xAxis = {
        axisLabel: '',
        showMaxMin: true,
        tickValues: function() {
            return ["0-1 month", "1-6 months", "6-12 months", "1-3 years", "3-6 years"];
        },
    };

    vm.getTooltipContent = function (dataInMonth, x) {
        var average = (dataInMonth.all !== 0) ? d3.format(".2%")(dataInMonth.y / dataInMonth.all) : 0;
        return "<div>Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services: <strong>"
            + $filter('indiaNumbers')(dataInMonth.all) + "</strong></div>"
            + "<div>% of children " + x + ": <strong>" + average + "</strong></div>";
    };

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        vm.filtersData.age = '';
        $location.search('gender', null);
        $location.search('age', null);
    };

    vm.resetOnlyAgeAdditionalFilter = function() {
        vm.filtersData.age = '';
        $location.search('age', null);
    };
}

EnrolledChildrenController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'demographicsService',
    'locationsService',
    'userLocationId',
    'storageService',
    'genders',
    'ages',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('enrolledChildren', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EnrolledChildrenController,
        controllerAs: '$ctrl',
    };
});
