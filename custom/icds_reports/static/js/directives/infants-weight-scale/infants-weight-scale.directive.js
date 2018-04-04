/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfantsWeightScaleController($scope, $routeParams, $location, $filter, infrastructureService,
    locationsService, userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "AWCs Reported Weighing Scale: Infants";
    vm.steps = {
        'map': {route: '/infants_weight_scale/map', label: 'Map View'},
        'chart': {route: '/infants_weight_scale/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a weighing scale for infants',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total of AWCs that reported having a weighing scale for infants: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: 'Percentage of AWCs that reported having a weighing scale for infants: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = infrastructureService.getInfantsWeightScaleData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

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
                    var dataInMonth = _.find(vm.chartData[0].values, function(num) { return num['x'] === d.value;});
                    return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), dataInMonth);

                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of AWCs that reported having a weighing scale for infants',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (monthName, dataInMonth) {
        var tooltip_content = "<p><strong>" + monthName + "</strong></p><br/>";
        tooltip_content += "<div>Number of AWCs that reported having a weighing scale for infants: <strong>" + $filter('indiaNumbers')(dataInMonth.in_month) + "</strong></div>";
        tooltip_content += "<div>Percentage of AWCs that reported having a weighing scale for infants: <strong>" + d3.format('.2%')(dataInMonth.y) + "</strong></div>";

        return tooltip_content;
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

InfantsWeightScaleController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'infrastructureService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('infantsWeightScale', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: InfantsWeightScaleController,
        controllerAs: '$ctrl',
    };
});
