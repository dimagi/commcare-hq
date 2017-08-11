/* global d3 */

function MapOrSectorController() {
    var vm = this;
    vm.height = vm.location && vm.location.location_type === 'block' ? 700 : 2000;

    vm.chartOptions = {
        chart: {
            type: 'multiBarHorizontalChart',
            height: vm.height,
            width: 1000,
            margin: {
                bottom: 120,
                left: 200,
            },
            x: function (d) {
                return d[0];
            },
            y: function (d) {
                return d[1];
            },
            showControls: false,
            showValues: false,
            duration: 500,
            xAxis: {
                showMaxMin: false,
            },
            yAxis: {
                tickFormat: function (d) {
                    return d3.format(".4r")(d);
                },
            },
        },
    };
}

MapOrSectorController.$inject = [];

var url = hqImport('hqwebapp/js/urllib').reverse;

window.angular.module('icdsApp').directive('mapOrSectorView', function() {
    return {
        restrict: 'E',
        scope: {
            mode: '@',
            data: '=',
            templatePopup: '&',
            location: '=',
        },
        templateUrl: url('icds-ng-template', 'map-or-sector-view.directive'),
        bindToController: true,
        controller: MapOrSectorController,
        controllerAs: '$ctrl',
    };
});
