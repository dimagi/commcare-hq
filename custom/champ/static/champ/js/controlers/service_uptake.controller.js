/* global moment, d3 */

function ServiceUptakeController(reportsDataService, filtersService) {
    var vm = this;
    vm.title = "Prevision VS Achievements Table";
    vm.filters = {
        month_start: 1,
        month_end: new Date().getMonth() + 1,
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

    vm.activityTypes = [
        {id: '', value: 'All'},
        {id: 'epm', value: 'EPM'},
        {id: 'mat_distribution', value: 'Material Distribution'},
    ];

    vm.visitsTypes = [
        {id: '', value: 'All'},
        {id: 'first_visit', value: 'First Visit'},
        {id: 'follow_up_visit', value: 'Follow Up Visit'},
    ];

    vm.clientTypes = [
        {id: '', value: 'All'},
        {id: 'FSW', value: 'FSW'},
        {id: 'MSM', value: 'MSM'},
        {id: 'client_fsw', value: 'Client FSW'},
    ];

    vm.organizations = [];


    for (var year=2014; year <= new Date().getFullYear(); year++ ) {
        vm.years.push({
            value: year,
            id: year,
        });
    }

    vm.getData = function() {
        reportsDataService.getServiceUptakeData(vm.filters).then(function (response) {
            vm.chartData = response.data.chart;
            vm.tickValues = response.data.tickValues;
            filtersService.districtFilter().then(function (response) {
                vm.districts = response.data.options;
            });
            filtersService.organizationFilter().then(function (response) {
                vm.organizations = response.data.options;
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
            duration: 100,
            xAxis: {
                axisLabel: '',
                tickFormat: function(d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function() {
                    return vm.tickValues;
                },
                showMaxMin: true,
            },
            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(".2%")(d);
                },
            },
        },
    };

    vm.onSelectOption = function($item, property) {
        if ($item.id === '') {
            vm.filters[property] = [$item.id];
        } else if (vm.filters[property].indexOf('') !== -1) {
            vm.filters[property] = [$item.id];
        }
    };
}

ServiceUptakeController.$inject = ['reportsDataService', 'filtersService'];