/* global d3 */

function MapOrSectorController() {
    var vm = this;
    vm.height = 750;

    vm.chartOptions = {
        chart: {
            type: 'multiBarHorizontalChart',
            height: vm.height,
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
            showValues: true,
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

var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').directive('mapOrSectorView', function() {
    return {
        restrict: 'E',
        scope: {
            mode: '@',
            data: '=',
            templatePopup: '&',
        },
        templateUrl: url('icds-ng-template', 'map-or-sector-view.directive'),
        bindToController: true,
        controller: MapOrSectorController,
        controllerAs: '$ctrl',
    };
});
