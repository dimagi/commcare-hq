var url = hqImport('hqwebapp/js/urllib.js').reverse;


function UnderweightChildrenReportController($routeParams, maternalChildService) {
    var vm = this;

    vm.filtersData = {};

    vm.step = $routeParams.step;
    vm.steps = [
        {route: '/underweight_children/1', label: 'MapView'},
        {route: '/underweight_children/2', label: 'ChartView'},
    ];
    vm.mapData = null;
    vm.chartData = null;

    vm.rightLegend = {
        average: 10,
        info: "Percentage of children with weight-for-age less than -2 standard deviations of the WHO Child Growth Standards median. Children who are moderately or severely underweight have a higher risk of mortality.",
    };

    maternalChildService.getUnderweightChildrenData().then(function(response) {
        vm.mapData = response.data.configs;
        vm.chartData = response.data.chart
        vm.chartTicks = vm.chartData[0].values.map(function(d) { return d[0]; })
    });

    vm.chartOptions = {
        chart: {
            type: 'lineChart',
            height: 450,
            margin : {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80
            },
            x: function(d){ return d[0]; },
            y: function(d){ return d[1]; },

            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function(d) {
                    return d3.time.format('%m/%d/%y')(new Date(d))
                },
                tickValues: function() {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(".0%")(d);
                },
                axisLabelDistance: 20,
            }
        }
    };
}

UnderweightChildrenReportController.$inject = ['$routeParams', 'maternalChildService'];

window.angular.module('icdsApp').directive('underweightChildrenReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'underweight-children-report.directive'),
        bindToController: true,
        controller: UnderweightChildrenReportController,
        controllerAs: '$ctrl',
    };
});
