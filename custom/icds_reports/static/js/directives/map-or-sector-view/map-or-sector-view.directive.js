/* global d3 */

function MapOrSectorController($location, storageService, locationsService) {
    var vm = this;
    var location_id = $location.search().location_id;

    vm.chartOptions = {

        chart: {
            type: 'multiBarHorizontalChart',
            width: 1400,
            height: 550,
            margin: {
                bottom: 40,
                left: 350,
            },
            x: function (d) {
                return d[0];
            },
            y: function (d) {
                return d[1];
            },
            showControls: false,
            showLegend: false,
            showValues: true,
            valueFormat: function (d) {
                if (vm.data.mapData.format === "number") {
                    return d;
                }
                return d3.format(".2%")(d);
            },
            xAxis: {
                showMaxMin: false,
            },
            yAxis: {
                tickFormat: function (d) {
                    if (vm.data.mapData.format === "number") {
                        return d3.format("d")(d);
                    }
                    return d3.format("%")(d);
                },
                axisLabelDistance: 20,
            },
            tooltip: function (x, y) {
                if (!vm.data.mapData.tooltips_data || !vm.data.mapData.tooltips_data[y]) {
                    return 'NA';
                }

                return vm.templatePopup({
                    loc: {
                        properties: {
                            name: y,
                        },
                    },
                    row: vm.data.mapData.tooltips_data[y],
                });
            },
            callback: function(chart) {
                var height = 550;
                var calc_height = vm.data.mapData ? vm.data.mapData.chart_data[0].values.length * 50 : 0;
                vm.chartOptions.chart.height = calc_height > height ? calc_height : height;

                chart.multibar.dispatch.on('elementClick', function (e) {
                    locationsService.getLocationByNameAndParent(e.point[0], location_id).then(function (locations) {
                        var location = locations[0];
                        $location.search('location_name', location.name);
                        $location.search('location_id', location.location_id);

                        storageService.setKey('search', $location.search());
                        if (location.location_type_name === 'awc') {
                            $location.path('awc_reports');
                        }
                    });
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: function () {
                return '<i class="fa fa-info-circle"></i> ' + (vm.data.mapData !== void(0) ? vm.data.mapData.info : "");
            },
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            },
        },
        title: {
            enable: true,
            text: vm.label,
            css: {
                'text-align': 'right',
                'color': 'black',
            },
        },
    };
}

MapOrSectorController.$inject = [ '$location', 'storageService', 'locationsService'];

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').directive('mapOrSectorView', function () {
    return {
        restrict: 'E',
        scope: {
            mode: '@',
            data: '=',
            templatePopup: '&',
            location: '=',
            label: '=',
        },
        templateUrl: url('icds-ng-template', 'map-or-sector-view.directive'),
        bindToController: true,
        controller: MapOrSectorController,
        controllerAs: '$ctrl',
    };
});
