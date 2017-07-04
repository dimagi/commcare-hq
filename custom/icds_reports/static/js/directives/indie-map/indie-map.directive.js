/* global d3, _, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */

function IndieMapController($scope, $compile, $location, storageService) {
    var vm = this;
    $scope.$watch(function () {
        return vm.data;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        if (newValue[0].data) {
            vm.map.data = newValue[0].data;
        }
        vm.map.fills = newValue[0].fills;
        vm.map.rightLegend = newValue[0].rightLegend;
        vm.indicator = newValue[0].slug;
    }, true);

    $scope.$watch(function () {
        return vm.bubbles;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.mapPluginData.bubbles = newValue;
    }, true);

    $scope.$watch(function () {
        return vm.rightLegend;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.map.rightLegend = newValue;
    }, true);
    $location.search(storageService.get());
    var location_level = $location.search()['selectedLocationLevel'];
    var location = $location.search()['location_name'];
    vm.type = '';

    if (location_level === void(0) || location_level === -1) {
        vm.scope = "ind";
        vm.type = vm.scope + "Topo";
        Datamap.prototype[vm.type] = STATES_TOPOJSON;
    } else if (location_level === 0) {
        vm.scope = location;
        vm.type = vm.scope + "Topo";
        Datamap.prototype[vm.type] = DISTRICT_TOPOJSON;
    } else if (location_level === 1) {
        vm.scope = location;
        vm.type = vm.scope + "Topo";
        Datamap.prototype[vm.type] = BLOCK_TOPOJSON;
    }

    vm.indicator = vm.data && vm.data[0] !== void(0) ? vm.data[0].slug : null;

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
        scope: vm.scope,
        rightLegend: vm.data && vm.data[0] !== void(0) ? vm.data[0].rightLegend : null,
        data: vm.data && vm.data[0] !== void(0) ? vm.data[0].data : null,
        fills: vm.data && vm.data[0] !== void(0) ? vm.data[0].fills : null,
        height: Datamap.prototype[vm.type].objects[vm.scope].height,
        setProjection: function (element) {
            var div = vm.scope === "ind" ? 3 : 2;
            var projection = d3.geo.equirectangular()
                .center(Datamap.prototype[vm.type].objects[vm.scope].center)
                .scale(Datamap.prototype[vm.type].objects[vm.scope].scale)
                .translate([element.offsetWidth / 2, element.offsetHeight / div]);
            var path = d3.geo.path()
                .projection(projection);

            return {path: path, projection: projection};
        },
    };

    vm.updateMap = function (geography) {
        $location.search('location_name', geography.id);
        storageService.set($location.search());
        $scope.$apply();
    };

    vm.mapPlugins = {
        bubbles: null,
    };
    vm.mapPluginData = {
        bubbles: [],
    };

    if (vm.map.data) {
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
                    .attr('style', 'width: 150px; left 5%; bottom: 40%; border: 1px solid black;')
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
                        .attr('style', 'position: absolute; width: 150px; bottom: 40%; right: 10%;')
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
                            '</label>',
                        ];
                        html.push(row.join(''));
                    });
                    var ele = d3.select(this.options.element).append('div')
                        .attr('class', '')
                        .attr('style', 'position: absolute; width: 100%; top: 5%; right: 25%;')
                        .html(html.join(''));
                    $compile(ele[0])($scope);
                }
            },
        });
    }

}

IndieMapController.$inject = ['$scope', '$compile', '$location', 'storageService'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=?',
            legendTitle: '@?',
            bubbles: '=?',
        },
        template: '<div class="indie-map-directive"><datamap on-click="$ctrl.updateMap" map="$ctrl.map" plugins="$ctrl.mapPlugins" plugin-data="$ctrl.mapPluginData"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
