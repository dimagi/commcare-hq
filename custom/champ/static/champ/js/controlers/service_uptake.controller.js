/* global moment */

function ServiceUptakeController($scope, reportsDataService, filtersService) {
    var vm = this;
    vm.title = "Prevision VS Achievements Table";
    vm.filters = {
        month_start: 1,
        month_end: new Date().getMonth(),
        year_start: new Date().getFullYear(),
        year_end:new Date().getFullYear(),
    };

    vm.months = [];
    vm.years = [];

    window.angular.forEach(moment.months(), function(key, value) {
        vm.months.push({
            value: key,
            id: value + 1,
        });
    });


    for (var year=2014; year <= new Date().getFullYear(); year++ ) {
        vm.years.push({
            value: year,
            id: year,
        });
    }

    vm.getData = function() {
        reportsDataService.getServiceUptakeData(vm.filters).then(function (response) {
            vm.chartData = response.data.chart;
            filtersService.districtFilter().then(function (response) {
                vm.districts = response.data.options;
            });
        });
    };
    vm.getData();

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
            x: function(d){ return d.x; },
            y: function(d){ return d.y; },
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
            xAxis: {
                axisLabel: '',
                tickFormat: function(d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(".2%")(d);
                },
            },
        }
    };
}

ServiceUptakeController.$inject = ['$scope', 'reportsDataService', 'filtersService'];