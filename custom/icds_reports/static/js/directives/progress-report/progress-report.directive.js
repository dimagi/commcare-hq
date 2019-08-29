/* global _, moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ProgressReportController($scope, $location, progressReportService,
    storageService, $routeParams, userLocationId, DTOptionsBuilder, DTColumnDefBuilder, haveAccessToAllLocations) {

    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];

    vm.filtersData = $location.search();
    vm.filters = ['gender', 'age'];
    vm.label = "ICDS-CAS Fact Sheets";
    vm.data = [];
    vm.dates = [];
    vm.now = new Date().getMonth() + 1;
    vm.previousMonth = moment().set('date', 1).subtract(1, 'days').format('MMMM YYYY');
    vm.currentMonth = moment().format("MMMM");
    vm.showPreviousMonthWarning = (
        storageService.getKey('search')['month'] === void(0) ||
        (
            vm.now === parseInt(storageService.getKey('search')['month']) &&
            new Date().getFullYear() === parseInt(storageService.getKey('search')['year'])
        )
    ) && (new Date().getDate() === 1 || new Date().getDate() === 2);
    vm.showWarning = (
        storageService.getKey('search')['month'] === void(0) ||
        (
            vm.now === parseInt(storageService.getKey('search')['month']) &&
            new Date().getFullYear() === parseInt(storageService.getKey('search')['year'])
        )
    ) && !vm.showPreviousMonthWarning;
    vm.report = $routeParams.report;

    vm.dtOptions = DTOptionsBuilder
        .newOptions()
        .withOption('scrollY', '400px')
        .withOption('scrollX', false)
        .withOption('scrollCollapse', true)
        .withOption('paging', false)
        .withOption('order', false)
        .withOption('sortable', false)
        .withDOM('<t>');

    vm.dtColumnDefs = [
        DTColumnDefBuilder.newColumnDef(0).notSortable(),
        DTColumnDefBuilder.newColumnDef(1).notSortable(),
        DTColumnDefBuilder.newColumnDef(2).notSortable(),
        DTColumnDefBuilder.newColumnDef(3).notSortable(),
        DTColumnDefBuilder.newColumnDef(4).notSortable(),
    ];
    vm.showTable = true;

    $scope.$on('filtersChange', function() {
        vm.showPreviousMonthWarning = (
            (
                vm.now === parseInt(storageService.getKey('search')['month']) &&
                new Date().getFullYear() === parseInt(storageService.getKey('search')['year'])
            ) &&
            (
                new Date().getDate() === 1 || new Date().getDate() === 2
            )
        );
        vm.showWarning = (
            vm.now === parseInt(storageService.getKey('search')['month']) &&
            new Date().getFullYear() === parseInt(storageService.getKey('search')['year'])
        ) && !vm.showPreviousMonthWarning;
        vm.loadData();
    });

    $scope.$watch(function() {
        return vm.selectedLocations;
    }, function (newValue, oldValue) {
        if (newValue === oldValue || !newValue || newValue.length === 0) {
            return;
        }
        if (newValue.length === 6) {
            var parent = newValue[3];
            $location.search('location_id', parent.location_id);
            $location.search('selectedLocationLevel', 3);
            $location.search('location_name', parent.name);
            storageService.setKey('message', true);
            setTimeout(function() {
                storageService.setKey('message', false);
            }, 3000);
        }
        return newValue;
    }, true);

    vm.loadData = function () {
        if (!vm.report) {
            return;
        }
        var params = window.angular.copy(vm.filtersData);
        params.category = vm.report;
        vm.myPromise = progressReportService.getData(params).then(function(response) {
            vm.title = response.data.config.title;
            vm.data = response.data.config.sections;
        });
    };

    vm.sumValues = function(values) {
        var sum = _.reduce(values, function(memo, num) { return memo + num; }, 0);
        return sum / values.length;
    };

    vm.getCSS = function(data, index, reverse) {
        if (index === 0 || index === 1) {
            return 'black';
        }

        var currentData = parseFloat(data[index].html.toFixed(2));
        var previousMonthData = parseFloat(data[index - 1].html.toFixed(2));

        var colors = (reverse ? ['red', 'green'] : ['green', 'red']);

        if (currentData === previousMonthData) {
            return 'black';
        } else if (previousMonthData < currentData) {
            return colors[0] + ' fa fa-arrow-up';
        } else if (previousMonthData > currentData) {
            return colors[1] + ' fa fa-arrow-down';
        }
    };

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


    vm.moveToLocation = function(loc, index) {
        if (loc === 'national') {
            $location.search('location_id', '');
            $location.search('selectedLocationLevel', -1);
            $location.search('location_name', '');
        } else {
            $location.search('location_id', loc.location_id);
            $location.search('selectedLocationLevel', index);
            $location.search('location_name', loc.name);
        }
    };

    vm.goToReport = function(reportName) {
        $location.path('fact_sheets/' + reportName);
    };

    vm.goBack = function() {
        vm.report = null;
        vm.title = null;
        $location.path('fact_sheets/');
    };

    vm.loadData();
}

ProgressReportController.$inject = [
    '$scope', '$location', 'progressReportService', 'storageService', '$routeParams', 'userLocationId', 'DTOptionsBuilder', 'DTColumnDefBuilder', 'haveAccessToAllLocations',
];

window.angular.module('icdsApp').directive('progressReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'progress-report.directive'),
        bindToController: true,
        controller: ProgressReportController,
        controllerAs: '$ctrl',
    };
});
