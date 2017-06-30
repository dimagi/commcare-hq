/* global d3*/

var url = hqImport('hqwebapp/js/urllib.js').reverse;

function PrevalenceOfStunningReportController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    $location.search(storageService.get());
    vm.filtersData = $location.search();
    vm.label = "Prevalence of Stunning (Height for age)";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/stunning/map', label: 'Map'},
        'chart': {route: '/stunning/chart', label: 'Chart'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.chartData = null;
    vm.top_three = [];
    vm.bottom_three = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of children between 6 - 60 months enrolled for ICDS services with weight-for-height below -3 standard deviations of the WHO Child Growth Standards median.',
    };

    vm.templatePopup = function(loc, row) {
        var total = $filter('indiaNumbers')(row ? row.total : 0);
        var sever = $filter('indiaNumbers')(row ? row.severe : 0);
        var moderate = $filter('indiaNumbers')(row ? row.moderate : 0);
        var normal = $filter('indiaNumbers')(row ? row.normal : 0);
        return '<div class="hoverinfo" style="max-width: 200px !important;"><p>' + loc.properties.name + '</p><p>' + vm.rightLegend.info + '</p>' + '<div>Total Children weighed in given month: <strong>' + total + '</strong></div><div>Severely Acute Malnutrition: <strong>' + sever + '</strong></div><div>Moderately Acute Malnutrition: <strong>' + moderate +'</strong></div><div>Normal: <strong>' + normal + '</strong></div></ul>';
    };

    vm.loadData = function () {
        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
        } else {
            vm.mode = 'map';
        }

        maternalChildService.getPrevalenceOfStunningData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
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
                left: 80,
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
                    return d3.time.format('%m/%d/%y')(new Date(d));
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
            },
        },
    };
}

PrevalenceOfStunningReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService'];

window.angular.module('icdsApp').directive('prevalenceOfStunning', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: PrevalenceOfStunningReportController,
        controllerAs: '$ctrl',
    };
});
