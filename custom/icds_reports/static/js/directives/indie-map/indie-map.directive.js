/* global d3 */

function IndieMapController($scope) {
    var vm = this;

    $scope.$watch(function() { return vm.data; }, function(newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.data = newValue;
    }, true);

    this.map = {
        scope: 'ind',
        zoomable: true,
        responsive: true,
        fills: {
            VERY_HIGH: '2171b5',
            HIGH: '#6baed6',
            MEDIUM: '#bcd6e7',
            LOW: '#eef2ff',
            defaultFill: '#eef2ff',
        },
        data: vm.data,
        setProjection: function(element) {
            var projection = d3.geo.mercator()
                .center([80, 25])
                .scale(1200)
                .translate([element.offsetWidth / 2, element.offsetHeight / 4]);
            var path = d3.geo.path()
                .projection(projection);

            return {path: path, projection: projection};
        },
    };
}

IndieMapController.$inject = ['$scope'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=',
        },
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
