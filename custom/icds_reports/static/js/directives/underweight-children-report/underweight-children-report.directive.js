var url = hqImport('hqwebapp/js/urllib.js').reverse;


function UnderweightChildrenReportController($scope, $routeParams, $location, maternalChildService,
                                             locationsService, userLocationId) {
    var vm = this;

    vm.filtersData = window.angular.copy($location.search());
    vm.label = "Prevalence of Undernutrition (weight-for-age)";
    vm.step = $routeParams.step;
    vm.steps = [
        {route: '/underweight_children/1', label: 'MapView'},
        {route: '/underweight_children/2', label: 'ChartView'},
    ];
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.chartData = null;
    vm.top_three = [];
    vm.bottom_three = [];
    vm.location_type = null;
    vm.loaded = false;

    vm.rightLegend = {
        average: 10,
        info: "Percentage of children with weight-for-age less than -2 standard deviations of the WHO Child Growth Standards median. Children who are moderately or severely underweight have a higher risk of mortality.",
    };

    vm.loadData = function () {
        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
        } else {
            vm.mode = 'map';
        }

        maternalChildService.getUnderweightChildrenData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "1") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "2") {
                vm.chartData = response.data.report_data.chart_data;
                vm.top_three = response.data.report_data.top_three;
                vm.bottom_three = response.data.report_data.bottom_three;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d[0]; });
            }
        });
    };

    var init = function() {
        var locationId = vm.filtersData.location || userLocationId;
        if (!locationId || locationId === 'all') {
            vm.loadData();
            vm.loaded = true;
            return;
        }
        locationsService.getLocation(locationId).then(function(location) {
            vm.location = location;
            vm.loadData();
            vm.loaded = true;
        });
    };

    init();


    $scope.$on('filtersChange', function() {
        vm.loadData();
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

UnderweightChildrenReportController.$inject = ['$scope', '$routeParams', '$location', 'maternalChildService', 'locationsService', 'userLocationId'];

window.angular.module('icdsApp').directive('underweightChildrenReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'underweight-children-report.directive'),
        bindToController: true,
        controller: UnderweightChildrenReportController,
        controllerAs: '$ctrl',
    };
});
