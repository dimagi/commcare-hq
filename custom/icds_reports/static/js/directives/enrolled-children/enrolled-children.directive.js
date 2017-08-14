/* global d3*/
var url = hqImport('hqwebapp/js/initial_page_data.js').reverse;

function EnrolledChildrenController($scope, $routeParams, $location, $filter, demographicsService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.label = "Children (0-6 years) who are enrolled for ICDS services";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/enrolled_children/map', label: 'Map'},
        'chart': {route: '/enrolled_children/chart', label: 'Chart'},
    };
    vm.data = {
        legendTitle: 'Number of Children',
    };
    vm.chartData = null;
    vm.top_three = [];
    vm.bottom_three = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = ['month'];

    vm.rightLegend = {
        info: 'Total number of children between the age of 0 - 6 years who are enrolled for ICDS services',
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
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total number of children between the age of 0 - 6 years who are enrolled for ICDS services: <strong>' + valid + '</strong></div>';
    };

    vm.loadData = function () {
        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
            vm.steps['map'].label = 'Sector';
        } else {
            vm.mode = 'map';
            vm.steps['map'].label = 'Map';
        }

        vm.myPromise = demographicsService.getEnrolledChildrenData(vm.step, vm.filtersData).then(function(response) {
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
            type: 'multiBarChart',
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
            useInteractiveGuideline: false,
            tooltip: function (key, x) {
                var data = _.find(vm.chartData[0].values, function(num) { return num.x === x;});

                var content = "<p>Total number of children between the age of 0 - 6 years who are enrolled for ICDS services: <strong>" + $filter('indiaNumbers')(data.all) + "</strong></p>";
                content += "<p>% of children " + x + ": <strong>" + d3.format(".2%")(data.y / data.all) + "</strong></p>";
                return content;
            },
            clipVoronoi: false,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickValues: function() {
                    return ["0-1 month", "1-6 months", "6-12 months", "1-3 years", "3-6 years"];
                },
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
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

EnrolledChildrenController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService'];

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
