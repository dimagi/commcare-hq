/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdhaarController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
    userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Percent Aadhaar-seeded Beneficiaries";
    vm.steps = {
        'map': {route: '/adhaar/map', label: 'Map View'},
        'chart': {route: '/adhaar/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage beneficiary',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Percentage of individuals registered using CAS whose Aadhaar identification has been captured',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of ICDS beneficiaries whose Aadhaar has been captured: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = demographicsService.getAdhaarData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init = function() {
        var locationId = vm.filtersData.location_id || vm.userLocationId;
        if (!locationId || ["all", "null", "undefined"].indexOf(locationId) >= 0) {
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
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
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
                    return d3.format(".2%")(d);
                },
                axisLabelDistance: 20,
                forceY: [0],
            },
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {
                    var day = _.find(vm.chartData[0].values, function(num) { return num['x'] === d.value; });
                    var tooltip_content = vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), day);
                    return tooltip_content;
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage number of ICDS beneficiaries whose Aadhaar identification has been captured',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.getTooltipContent = function(monthName, day) {
        var content = "<p><strong>" + monthName + "</strong></p><br/>";
        content += "<div>Total number of ICDS beneficiaries whose Aadhaar has been captured: <strong>" + $filter('indiaNumbers')(day.in_month) + "</strong></div>";
        content += "<div>% of ICDS beneficiaries whose Aadhaar has been captured: <strong>" + d3.format('.2%')(day.y) + "</strong></div>";
        return content;
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

AdhaarController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'baseControllersService'];

window.angular.module('icdsApp').directive('adhaarBeneficiary', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdhaarController,
        controllerAs: '$ctrl',
    };
});
