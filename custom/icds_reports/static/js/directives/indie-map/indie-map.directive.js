/* global d3, _ */

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
        fills: vm.fills,
        data: vm.data,
        aspectRatio: 0.5,
        height: 800,
        setProjection: function(element) {
            var projection = d3.geo.equirectangular()
                .center([80, 25])
                .scale(1240)
                .translate([element.offsetWidth / 2, element.offsetHeight / 2]);
            var path = d3.geo.path()
                .projection(projection);

            return {path: path, projection: projection};
        },
    };

    vm.mapPlugins = vm.mapPlugins || {};
    _.extend(vm.mapPlugins, {
        customLegend: function() {
            var html = ['<h3>' + vm.legendTitle + '</h3><table style="margin: 0 auto;">'];
            for (var fillKey in this.options.fills) {
                if (fillKey === 'defaultFill') continue;
                html.push('<tr><td style="background-color: ' + this.options.fills[fillKey] + '; width: 45px; height: 45px;">',
                          '<td/><td style="padding-left: 5px;">' + fillKey + '</td></tr>');
            }
            html.push('</table>');
            d3.select(this.options.element).append('div')
                .attr('class', 'datamaps-legend text-center')
                .attr('style', 'width: 150px; bottom: 5%; border: 1px solid black;')
                .html(html.join(''));
        },
    });
}

IndieMapController.$inject = ['$scope'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=',
            legendTitle: '@?',
            fills: '=?',
            mapPlugins: '=?',
        },
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map" plugins="$ctrl.mapPlugins"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
