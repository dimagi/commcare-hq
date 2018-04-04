/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCDailyStatusController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
    userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWC Daily Status";
    vm.steps = {
        'map': {route: '/awc_daily_status/map', label: 'Map View'},
        'chart': {route: '/awc_daily_status/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage AWCs',
    };
    vm.filters = ['month', 'age', 'gender'];
    vm.rightLegend = {
        info: 'Percentage of Angwanwadi Centers that were open yesterday',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var inDay = row ? $filter('indiaNumbers')(row.in_day) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_day / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of AWCs that were open yesterday: ',
                indicator_value: inDay,
            },
            {
                indicator_name: 'Total number of AWCs that have been launched: ',
                indicator_value: total,
            },
            {
                indicator_name: '% of AWCs open yesterday: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = false;
        var forceYAxisFromZero = true;
        vm.myPromise = icdsCasReachService.getAwcDailyStatusData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    $scope.$on('filtersChange', function() {
        vm.loadData();
    });

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key !== null && key.location_id === vm.userLocationId) {
                i = value;
            }
        });
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

            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
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
                rotateLabels: -45,
            },
            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
                forceY: [0],
            },
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return num.x === date; });
                        return day.y;
                    };
                    var total = findValue(vm.chartData[0].values, d.value);
                    var value = findValue(vm.chartData[1].values, d.value);
                    return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), value, total);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Total Number of Angwanwadi Centers that were open yesterday',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function(monthName, value, total) {
        return "<div>Total number of AWCs that were open on <strong>" + monthName + "</strong>: <strong>" + $filter('indiaNumbers')(value) + "</strong></div>"
        + "<div>Total number of AWCs that have been launched: <strong>" + $filter('indiaNumbers')(total) + "</strong></div>"
        + "<div>% of AWCs open on <strong>" + monthName + "</strong>: <strong>" + d3.format('.2%')(value / (total || 1)) + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

AWCDailyStatusController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'icdsCasReachService', 'locationsService', 'userLocationId', 'storageService', 'baseControllersService'];

window.angular.module('icdsApp').directive('awcDailyStatus', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCDailyStatusController,
        controllerAs: '$ctrl',
    };
});
