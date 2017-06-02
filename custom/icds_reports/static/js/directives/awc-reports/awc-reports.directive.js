/* global d3, _ */

var url = hqImport('hqwebapp/js/urllib.js').reverse;

function AwcReportsController($http, $location, $routeParams, $log) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.tooltipPlacement = "right";
    vm.step = $routeParams.step;
    vm.data = [];

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

    vm.getDataForStep(vm.step);

    vm.chartOptions = {
        chart: {
            type: 'multiBarChart',
            height: 450,
            margin : {
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            },
            x: function(d){return d[0];},
            y: function(d){return d[1];},
            showValues: true,
            useInteractiveGuideline: true,
            clipVoronoi: false,
            duration: 500,
            xAxis: {
                axisLabel: '',
                tickFormat: function(d) {
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
        }
    };

    vm.steps ={
        system_usage: { route: "/awc_reports/system_usage", label: "System Usage"},
        pse: { route: "/awc_reports/pse", label: "Primary School Education (PSE)"},
        maternal_child: { route: "/awc_reports/maternal_child", label: "Maternal & Child Health"},
        demographics: { route: "/awc_reports/demographics", label: "Demographics"},
        beneficiary: { route: "/awc_reports/beneficiary", label: "Beneficiary List"},
    };

}

AwcReportsController.$inject = ['$http','$location', '$routeParams', '$log'];

window.angular.module('icdsApp').directive('awcReports', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-reports'),
        bindToController: true,
        controller: AwcReportsController,
        controllerAs: '$ctrl',
    };
});
