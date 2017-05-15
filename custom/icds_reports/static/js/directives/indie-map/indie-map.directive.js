/* global d3 */

function IndieMapController($scope) {
    var vm = this;
    $scope.$watch(function() { return vm.data; }, function(newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.data = newValue;
    }, true);

    vm.map = {
        scope: 'ind',
        aspectRatio: 0.5,

        options: {
        },
        zoomable: true,
        responsive: true,
        fills: vm.fills,
        data: vm.data,
        setProjection: function(element) {
            var projection = d3.geo.mercator()
                .center([80, 25])
                .scale(1240)
                .translate([element.offsetWidth / 2, element.offsetHeight / 4]);
            var path = d3.geo.path()
                .projection(projection);

            return {path: path, projection: projection};
        },
    };

    vm.mapPlugins = {
        customLegend: function() {
            var html = ['<h3>' + vm.legendTitle + '</h3><ul>'];
            for (var fillKey in this.options.fills) {
                if (fillKey === 'defaultFill') continue;
                html.push('<li class="key"><div style="background-color: ' + this.options.fills[fillKey] + '; width: 45px; height: 45px; display: inline-block"></div>',
                          '<span style="padding-left: 10px;">', fillKey, '</span></li>');
            }
            html.push('</ul>');
            d3.select(this.options.element).append('div')
                .attr('class', 'datamaps-legend')
                .attr('style', 'width: 200px; bottom: 20%; left: 20%')
                .html(html.join(''));
        },
    };
}

IndieMapController.$inject = ['$scope'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=',
            legendTitle: '@',
            fills: '=',
        },
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map" plugins="$ctrl.mapPlugins"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
