/* global d3, _ */

var weight_for_age = {
    F: {
        'red': [
            {x: 0, y: 2},
            {x: 1, y: 2.7},
            {x: 2, y: 3.3},
            {x: 3, y: 3.9},
            {x: 4, y: 4.4},
            {x: 5, y: 4.8},
            {x: 6, y: 5.1},
            {x: 7, y: 5.3},
            {x: 8, y: 5.6},
            {x: 9, y: 5.8},
            {x: 10, y: 5.9},
            {x: 11, y: 6.1},
            {x: 12, y: 6.3},
            {x: 13, y: 6.4},
            {x: 14, y: 6.6},
            {x: 15, y: 6.7},
            {x: 16, y: 6.9},
            {x: 17, y: 7},
            {x: 18, y: 7.2},
            {x: 19, y: 7.3},
            {x: 20, y: 7.5},
            {x: 21, y: 7.6},
            {x: 22, y: 7.8},
            {x: 23, y: 7.9},
            {x: 24, y: 8.1},
            {x: 25, y: 8.2},
            {x: 26, y: 8.4},
            {x: 27, y: 8.5},
            {x: 28, y: 8.6},
            {x: 29, y: 8.8},
            {x: 30, y: 8.9},
            {x: 31, y: 9},
            {x: 32, y: 9.1},
            {x: 33, y: 9.3},
            {x: 34, y: 9.4},
            {x: 35, y: 9.5},
            {x: 36, y: 9.6},
            {x: 37, y: 9.7},
            {x: 38, y: 9.8},
            {x: 39, y: 9.9},
            {x: 40, y: 10.1},
            {x: 41, y: 10.2},
            {x: 42, y: 10.3},
            {x: 43, y: 10.4},
            {x: 44, y: 10.5},
            {x: 45, y: 10.6},
            {x: 46, y: 10.7},
            {x: 47, y: 10.8},
            {x: 48, y: 10.9},
            {x: 49, y: 11},
            {x: 50, y: 11.1},
            {x: 51, y: 11.2},
            {x: 52, y: 11.3},
            {x: 53, y: 11.4},
            {x: 54, y: 11.5},
            {x: 55, y: 11.6},
            {x: 56, y: 11.7},
            {x: 57, y: 11.8},
            {x: 58, y: 11.9},
            {x: 59, y: 12},
            {x: 60, y: 12.1},
            {x: 61, y: 12.352},
            {x: 62, y: 12.456},
            {x: 63, y: 12.559},
            {x: 64, y: 12.662},
            {x: 65, y: 12.764},
            {x: 66, y: 12.866},
            {x: 67, y: 12.968},
            {x: 68, y: 13.069},
            {x: 69, y: 13.169},
            {x: 70, y: 13.27},
            {x: 71, y: 13.371},
            {x: 72, y: 13.471},
        ],
        'orange': [
            {x: 0, y: 0.4},
            {x: 1, y: 0.4},
            {x: 2, y: 0.5},
            {x: 3, y: 0.5},
            {x: 4, y: 0.6},
            {x: 5, y: 0.6},
            {x: 6, y: 0.6},
            {x: 7, y: 0.7},
            {x: 8, y: 0.7},
            {x: 9, y: 0.7},
            {x: 10, y: 0.8},
            {x: 11, y: 0.8},
            {x: 12, y: 0.7},
            {x: 13, y: 0.8},
            {x: 14, y: 0.8},
            {x: 15, y: 0.9},
            {x: 16, y: 0.8},
            {x: 17, y: 0.9},
            {x: 18, y: 0.9},
            {x: 19, y: 0.9},
            {x: 20, y: 0.9},
            {x: 21, y: 1},
            {x: 22, y: 0.9},
            {x: 23, y: 1},
            {x: 24, y: 0.9},
            {x: 25, y: 1},
            {x: 26, y: 1},
            {x: 27, y: 1},
            {x: 28, y: 1.1},
            {x: 29, y: 1},
            {x: 30, y: 1.1},
            {x: 31, y: 1.1},
            {x: 32, y: 1.2},
            {x: 33, y: 1.1},
            {x: 34, y: 1.1},
            {x: 35, y: 1.2},
            {x: 36, y: 1.2},
            {x: 37, y: 1.2},
            {x: 38, y: 1.3},
            {x: 39, y: 1.3},
            {x: 40, y: 1.2},
            {x: 41, y: 1.3},
            {x: 42, y: 1.3},
            {x: 43, y: 1.3},
            {x: 44, y: 1.3},
            {x: 45, y: 1.4},
            {x: 46, y: 1.4},
            {x: 47, y: 1.4},
            {x: 48, y: 1.4},
            {x: 49, y: 1.4},
            {x: 50, y: 1.5},
            {x: 51, y: 1.5},
            {x: 52, y: 1.5},
            {x: 53, y: 1.5},
            {x: 54, y: 1.5},
            {x: 55, y: 1.6},
            {x: 56, y: 1.6},
            {x: 57, y: 1.6},
            {x: 58, y: 1.6},
            {x: 59, y: 1.6},
            {x: 60, y: 1.6},
            {x: 61, y: 1.609},
            {x: 62, y: 1.627},
            {x: 63, y: 1.645},
            {x: 64, y: 1.662},
            {x: 65, y: 1.68},
            {x: 66, y: 1.698},
            {x: 67, y: 1.715},
            {x: 68, y: 1.732},
            {x: 69, y: 1.75},
            {x: 70, y: 1.768},
            {x: 71, y: 1.785},
            {x: 72, y: 1.803},
        ],
        'green': [
            {x: 0, y: 1.8},
            {x: 1, y: 2.3},
            {x: 2, y: 2.7},
            {x: 3, y: 2.9},
            {x: 4, y: 3.2},
            {x: 5, y: 3.4},
            {x: 6, y: 3.6},
            {x: 7, y: 3.8},
            {x: 8, y: 3.9},
            {x: 9, y: 4},
            {x: 10, y: 4.2},
            {x: 11, y: 4.3},
            {x: 12, y: 4.5},
            {x: 13, y: 4.6},
            {x: 14, y: 4.7},
            {x: 15, y: 4.8},
            {x: 16, y: 4.9},
            {x: 17, y: 5},
            {x: 18, y: 5.1},
            {x: 19, y: 5.3},
            {x: 20, y: 5.3},
            {x: 21, y: 5.4},
            {x: 22, y: 5.6},
            {x: 23, y: 5.7},
            {x: 24, y: 5.8},
            {x: 25, y: 5.9},
            {x: 26, y: 6},
            {x: 27, y: 6.2},
            {x: 28, y: 6.3},
            {x: 29, y: 6.4},
            {x: 30, y: 6.5},
            {x: 31, y: 6.7},
            {x: 32, y: 6.8},
            {x: 33, y: 6.9},
            {x: 34, y: 7.1},
            {x: 35, y: 7.2},
            {x: 36, y: 7.3},
            {x: 37, y: 7.5},
            {x: 38, y: 7.6},
            {x: 39, y: 7.8},
            {x: 40, y: 7.9},
            {x: 41, y: 8},
            {x: 42, y: 8.2},
            {x: 43, y: 8.4},
            {x: 44, y: 8.6},
            {x: 45, y: 8.7},
            {x: 46, y: 8.8},
            {x: 47, y: 9},
            {x: 48, y: 9.2},
            {x: 49, y: 9.4},
            {x: 50, y: 9.5},
            {x: 51, y: 9.7},
            {x: 52, y: 9.8},
            {x: 53, y: 10},
            {x: 54, y: 10.2},
            {x: 55, y: 10.3},
            {x: 56, y: 10.5},
            {x: 57, y: 10.7},
            {x: 58, y: 10.9},
            {x: 59, y: 11},
            {x: 60, y: 11.2},
            {x: 61, y: 10.939},
            {x: 62, y: 11.007},
            {x: 63, y: 11.159},
            {x: 64, y: 11.313},
            {x: 65, y: 11.467},
            {x: 66, y: 11.621},
            {x: 67, y: 11.777},
            {x: 68, y: 11.934},
            {x: 69, y: 12.092},
            {x: 70, y: 12.25},
            {x: 71, y: 12.41},
            {x: 72, y: 12.571},
        ],
    },
    M: [],
};

var url = hqImport('hqwebapp/js/urllib.js').reverse;

function AwcReportsController($scope, $http, $location, $routeParams, $log, DTOptionsBuilder) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.tooltipPlacement = "right";
    vm.step = $routeParams.step;
    vm.data = [];
    vm.filters = [];
    vm.dtOptions = DTOptionsBuilder.newOptions().withBootstrap().withOption('scrollX', '100%');
    vm.showTable = true;
    vm.showBeneficiary = false;
    vm.beneficiary = null;
    vm.xTicks = [];

    vm.getDataForStep = function(step) {
        var get_url = url('awc_reports', step);
        $http({
            method: "GET",
            url: get_url,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data;
            },
            function (error) {
                $log.error(error);
            }
        );
    };

    vm.getPopoverContent = function (data, type) {
        var html = '';
        if (type === 'weight' || type === 'both') {
            html += '<div>Weight: ' + (data.recorded_weight !== void(0) ? data.recorded_weight : "---") + '</div>';
        }
        if (type === 'height' || type === 'both') {
            html += '<div>Height: ' + (data.recorded_height !== void(0) ? data.recorded_height : "---") + '</div>';
        }
        return html;
    };

    vm.getDataForStep(vm.step);

    vm.chartOptions = {
        chart: {
            type: 'multiBarChart',
            height: 450,
            margin: {
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            },
            x: function (d) {
                return d[0];
            },
            y: function (d) {
                return d[1];
            },
            showValues: true,
            useInteractiveGuideline: true,
            clipVoronoi: false,
            duration: 500,
            xAxis: {
                axisLabel: '',
                tickFormat: function (d) {
                    if (typeof d === 'number') {
                        return d3.time.format('%m/%d/%y')(new Date(d));
                    } else if (typeof d === 'string') {
                        return d;
                    }
                },
            },
            yAxis: {
                axisLabel: '',
            },
        },
    };

    vm.beneficiaryChartOptions = {
        chart: {
            type: 'multiChart',
            height: 450,
            margin: {
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            },
            x: function(d){ return d.x; },
            y: function(d){ return d.y; },
            useVoronoi: false,
            clipEdge: true,
            duration: 100,
            useInteractiveGuideline: true,
            xAxis: {
                axisLabel: 'Months',
                showMaxMin: true,
                tickValues: function() {
                    return vm.xTicks;
                },
            },
            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format("d")(d);
                },
            },
            yAxis1: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format("d")(d);
                }
            },
        },
    };
    vm.beneficiaryChartOneData = [];
    vm.beneficiaryChartTwoData = [];

    vm.showBeneficiaryDetails = function(beneficiary){
        vm.beneficiary = beneficiary;
        vm.lineChartOneData = [];
        var lowest_age = 1000000;
        var highest_age = 0;
        var sex = null;
        window.angular.forEach(beneficiary, function (value) {
            lowest_age = lowest_age > value.age_in_months ? value.age_in_months : lowest_age;
            highest_age = highest_age < value.age_in_months ? value.age_in_months : highest_age;
            sex = value.sex;
            vm.lineChartOneData.push({
                x: value.age_in_months,
                y: value.recorded_weight,
            });
        });
        vm.xTicks = _.range(lowest_age - 1, highest_age + 2);

        setTimeout(function () {
            vm.beneficiaryChartOneData = [
                {
                    key: 'test1',
                    type: 'area',
                    values: weight_for_age[sex]['red'].slice(lowest_age - 1, highest_age + 2),
                    color: 'red',
                    yAxis: 1,
                },
                {
                    key: 'test2',
                    type: 'area',
                    values: weight_for_age[sex]['orange'].slice(lowest_age - 1, highest_age + 2),
                    color: 'orange',
                    yAxis: 1,
                },
                {
                    key: 'test3',
                    type: 'area',
                    values: weight_for_age[sex]['green'].slice(lowest_age - 1, highest_age + 2),
                    color: 'green',
                    yAxis: 1,
                },
                {
                    key: 'line',
                    type: 'line',
                    values: vm.lineChartOneData,
                    color: 'black',
                    yAxis: 1,
                }
            ];
            $scope.$apply();
        }, 500);


        vm.steps[vm.step].label = "Beneficiary Details";
        vm.showBeneficiary = true;
        vm.showTable = false;
    };

    vm.showBeneficiaryTable = function(){
        vm.beneficiary = null;
        vm.steps[vm.step].label = "Beneficiary List";
        vm.showBeneficiary = false;
        vm.showTable = true;
    };

    vm.steps ={
        system_usage: { route: "/awc_reports/system_usage", label: "System Usage"},
        pse: { route: "/awc_reports/pse", label: "Primary School Education (PSE)"},
        maternal_child: { route: "/awc_reports/maternal_child", label: "Maternal & Child Health"},
        demographics: { route: "/awc_reports/demographics", label: "Demographics"},
        beneficiary: { route: "/awc_reports/beneficiary", label: "Beneficiary List"},
    };

}

AwcReportsController.$inject = ['$scope', '$http', '$location', '$routeParams', '$log', 'DTOptionsBuilder'];

window.angular.module('icdsApp').directive('awcReports', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-reports'),
        bindToController: true,
        controller: AwcReportsController,
        controllerAs: '$ctrl',
    };
});
