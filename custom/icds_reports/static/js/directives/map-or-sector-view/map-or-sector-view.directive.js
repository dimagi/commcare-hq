/* global d3 */

function MapOrSectorController($scope) {
    var vm = this;

    setTimeout(function() {
        vm.chartOptions = {
            chart: {
                type: 'multiBarHorizontalChart',
                height: vm.data.mapData.chart_data[0].values.length < 8 ? 450 : vm.data.mapData.chart_data[0].values.length * 60,
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
        $scope.$apply();
    }, 500);
}

MapOrSectorController.$inject = ['$scope'];

var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').directive('mapOrSectorView', function() {
    return {
        restrict: 'E',
        scope: {
            mode: '@',
            data: '=',
        },
        templateUrl: url('icds-ng-template', 'map-or-sector-view.directive'),
        bindToController: true,
        controller: MapOrSectorController,
        controllerAs: '$ctrl',
    };
});
