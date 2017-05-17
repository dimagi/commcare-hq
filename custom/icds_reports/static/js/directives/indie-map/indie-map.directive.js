/* global d3, _ */

function IndieMapController($scope) {
    var vm = this;
    $scope.$watch(function() { return vm.data; }, function(newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.data = newValue;
    }, true);

    $scope.$watch(function() { return vm.rightLegend; }, function(newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.rightLegend = newValue;
    }, true);

    vm.map = {
        scope: 'ind',
        fills: vm.fills,
        rightLegend: vm.rightLegend,
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

    vm.mapPlugins = {};
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
    _.extend(vm.mapPlugins, {
        customTable: function() {
            var html = [
                '<table style="width: 250px;">',
                '<td style="border-right: 1px solid black; padding-right: 10px; padding-bottom: 10px; font-size: 2em;"><i class="fa fa-line-chart" aria-hidden="true"></i></td>',
                '<td style="padding-left: 10px; padding-bottom: 10px;">Average: ' + this.options.rightLegend['average'] + '%</td>',
                '<tr/>',
                '<tr>',
                '<td style="border-right: 1px solid black; font-size: 2em;"><i class="fa fa-info" aria-hidden="true"></td>',
                '<td style="padding-left: 10px;">' + this.options.rightLegend['info']+ '</td>',
                '<tr/>',
                '<tr>',
                '<td style="border-right: 1px solid black; font-size: 2em;"><i class="fa fa-clock-o" aria-hidden="true"></td>',
                '<td style="padding-left: 10px;">Last updated: 1/5/2017 | Monthly</td>',
                '<tr/>',
                '</table>',
            ];
            d3.select(this.options.element).append('div')
                .attr('class', '')
                .attr('style', 'position: absolute; width: 150px; bottom: 5%; right: 25%;')
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
            rightLegend: '=?',
        },
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map" plugins="$ctrl.mapPlugins"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
