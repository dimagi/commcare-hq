/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCSCoveredController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
    userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Launched";
    vm.steps = {
        'map': {route: '/awcs_covered/map', label: 'Map View'},
        'chart': {route: '/awcs_covered/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.filters = ['age', 'gender'];

    vm.templatePopup = function(loc, row) {
        var awcs = row ? $filter('indiaNumbers')(row.awcs) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<p>' + vm.rightLegend.info + '</p>' +
            '<div>Number of AWCs Launched: <strong>' + awcs + '</strong></div></div>';
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = false;
        var forceYAxisFromZero = false;
        vm.myPromise = icdsCasReachService.getAwcsCoveredData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    $scope.$on('filtersChange', function() {
        vm.loadData();
    });

    vm.getDisableIndex = function () {
        var i = -1;
        if (!haveAccessToAllLocations) {
            window.angular.forEach(vm.selectedLocations, function (key, value) {
                if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                    i = value;
                }
            });
        }
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
            width: 1100,
            margin: {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80,
            },
            x: function (d) {
                return d.x;
            },
            y: function (d) {
                return d.y;
            },
            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function (d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function () {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function (d) {
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
                forceY: [0],
            },
            callback: function (chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return num['x'] === date; });
                        return d3.format(",")(day['y']);
                    };

                    var tooltipContent = vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), findValue(vm.chartData[0].values, d.value));
                    return tooltipContent;
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> ' + vm.data.legendTitle,
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            },
        },
    };

    vm.tooltipContent = function(monthName, value) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + vm.data.legendTitle
            + "<div>Number of AWCs Launched: <strong>" + value + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

AWCSCoveredController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'icdsCasReachService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('awcsCovered', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCSCoveredController,
        controllerAs: '$ctrl',
    };
});
