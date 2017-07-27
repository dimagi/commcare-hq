/* global d3*/
var url = hqImport('hqwebapp/js/urllib.js').reverse;

function NewbornWithLowBirthController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.label = "% Newborns with Low Birth Weight";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/low_birth/map', label: 'Map'},
        'chart': {route: '/low_birth/chart', label: 'Chart'},
    };
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.chartData = null;
    vm.top_three = [];
    vm.bottom_three = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of newborns with born with birth weight less than 2500 grams.',
    };

    vm.message = storageService.getKey('message') || false;

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

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var low_birth = row ? $filter('indiaNumbers')(row.low_birth) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important;"><p>' + loc.properties.name + '</p><p>' + vm.rightLegend.info + '</p>' + '<div>Total Number of Newborns born in given month: <strong>' + total + '</strong></div><div>Number of Newborns with LBW in given month: <strong>' + low_birth + '</strong></div></ul>';
    };

    vm.loadData = function () {
        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
            vm.steps['map'].label = 'Sector';
        } else {
            vm.mode = 'map';
            vm.steps['map'].label = 'Map';
        }

        vm.myPromise = maternalChildService.getNewbornLowBirthData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.all_locations = response.data.report_data.all_locations;
                vm.top_three = response.data.report_data.top_three;
                vm.bottom_three = response.data.report_data.bottom_three;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d.x; });
            }
        });
    };

    var init = function() {
        var locationId = vm.filtersData.location_id || userLocationId;
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
            width: 1100,
            margin : {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80,
            },
            x: function(d){ return d.x; },
            y: function(d){ return d.y; },

            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function(d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function() {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
            },
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === date;});
                        return d3.format(",")(day['y']);
                    };

                    var tooltip_content = "<p><strong>" + d.value + "</strong></p><br/>";
                    tooltip_content += "<p>Total Number of Newborns born in given month: <strong>" + findValue(vm.chartData[0].values, d.value) + "</strong></p>";
                    tooltip_content += "<p>Number of Newborns with LBW in given month: <strong>" + findValue(vm.chartData[1].values, d.value) + "</strong></p>";
                    tooltip_content += "<span>Percentage of newborns born with birth weight less than 2500 grams</span>";

                    return tooltip_content;
                });
                return chart;
            },
        },
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

    vm.showNational = function () {
        return !isNaN($location.search()['selectedLocationLevel']) && parseInt($location.search()['selectedLocationLevel']) >= 0;
    };
}

NewbornWithLowBirthController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService'];

window.angular.module('icdsApp').directive('newbornLowWeight', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: NewbornWithLowBirthController,
        controllerAs: '$ctrl',
    };
});
