/* global d3, _ */

function IndieMapController($scope, $compile) {
    var vm = this;
    $scope.$watch(function () {
        return vm.data;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.data = newValue[0].data;
        vm.map.fills = newValue[0].fills;
        vm.map.rightLegend = newValue[0].rightLegend;
        vm.indicator = newValue[0].slug;
    }, true);

    $scope.$watch(function () {
        return vm.rightLegend;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.rightLegend = newValue;
    }, true);

    vm.indicator = vm.data[0] !== void(0) ? vm.data[0].slug : null;

    vm.changeIndicator = function (value) {
        window.angular.forEach(vm.data, function(row) {
            if (row.slug === value) {
                vm.map.data = row.data;
                vm.map.fills = row.fills;
                vm.map.rightLegend = row.rightLegend;
            }
        });
        vm.indicator = value;
    };
    vm.map = {
        scope: 'ind',
        rightLegend: vm.data[0] !== void(0) ? vm.data[0].rightLegend : null,
        data: vm.data[0] !== void(0) ? vm.data[0].data : null,
        fills: vm.data[0] !== void(0) ? vm.data[0].fills : null,
        aspectRatio: 0.5,
        height: 800,
        setProjection: function (element) {
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
        customLegend: function () {
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
        customTable: function () {
            if (this.options.rightLegend !== null) {
                var html = [
                    '<table style="width: 250px;">',
                    '<td style="border-right: 1px solid black; padding-right: 10px; padding-bottom: 10px; font-size: 2em;"><i class="fa fa-line-chart" aria-hidden="true"></i></td>',
                    '<td style="padding-left: 10px; padding-bottom: 10px;">Average: ' + this.options.rightLegend['average'] + '%</td>',
                    '<tr/>',
                    '<tr>',
                    '<td style="border-right: 1px solid black; font-size: 2em;"><i class="fa fa-info" aria-hidden="true"></td>',
                    '<td style="padding-left: 10px;">' + this.options.rightLegend['info'] + '</td>',
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
            }
        },
    });

    _.extend(vm.mapPlugins, {
        indicators: function () {
            var data = vm.data;
            if (data.length > 1) {
                var html = [];
                window.angular.forEach(data, function (indi) {
                    var row = [
                        '<label class="radio-inline" style="float: right; margin-left: 10px;">',
                        '<input type="radio" ng-model="$ctrl.indicator" ng-change="$ctrl.changeIndicator(\'' + indi.slug + '\')" ng-checked="$ctrl.indicator == \'' + indi.slug + '\'" name="indi" ng-value="' + indi.slug + '">' + indi.label,
                        '</label>'
                    ];
                    html.push(row.join(''))
                });
                var ele = d3.select(this.options.element).append('div')
                    .attr('class', '')
                    .attr('style', 'position: absolute; width: 100%; top: 5%; right: 25%;')
                    .html(html.join(''));
                $compile(ele[0])($scope)
            }
        },
    });

}

IndieMapController.$inject = ['$scope', '$compile'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=',
            legendTitle: '@?',
        },
        template: '<div class="indie-map-directive"><datamap map="$ctrl.map" plugins="$ctrl.mapPlugins"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
