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
        controller: function() {
            var vm = this;

            vm.chartOptions = {
                chart: {
                    type: 'multiBarHorizontalChart',
                    height: 450,
                    x: function(d){return d[0];},
                    y: function(d){return d[1];},
                    showControls: false,
                    showValues: true,
                    duration: 500,
                    xAxis: {
                        showMaxMin: false
                    },
                },
            };

        },
        controllerAs: '$ctrl',
    };
});
