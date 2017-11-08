/* global d3, _, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */

function IndieMapController($scope, $compile, $location, $filter, storageService, locationsService) {
    var vm = this;

    setTimeout(function() {
        $scope.$watch(function () {
            return vm.data;
        }, function (newValue, oldValue) {
            if (newValue === oldValue) {
                return;
            }
            if (newValue[0].data) {
                vm.map.data = getData(newValue[0]);
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

        if (Object.keys($location.search()).length === 0) {
            $location.search(storageService.getKey('search'));
        } else {
            storageService.setKey('search', $location.search());
        }

        var location_level = parseInt($location.search()['selectedLocationLevel']);
        var location_id = $location.search().location_id;
        var location = $location.search()['location_name'];
        vm.type = '';

        if (location_level === void(0) || isNaN(location_level) || location_level === -1 || location_level === 4) {
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

        var capitalize = function(str) {
            return str.replace(/(?:^|\s)\S/g, function(a) { return a.toUpperCase(); });
        };

        var getData = function(data) {
            var mapData = data && data[0] !== void(0) ? data[0].data : null;
            if (!mapData) {
                return null;
            }
            
            var formattedData = {};
            Object.keys(mapData).forEach(function(key) {
                formattedData[capitalize(key.toLowerCase())] = mapData[key];
            });
            return formattedData;
        };

        vm.map = {
            scope: vm.scope,
            rightLegend: vm.data && vm.data[0] !== void(0) ? vm.data[0].rightLegend : null,
            label: vm.data && vm.data[0] !== void(0) ? vm.data[0].label : null,
            data: getData(vm.data),
            fills: vm.data && vm.data[0] !== void(0) ? vm.data[0].fills : null,
            height: Datamap.prototype[vm.type].objects[vm.scope].height,
            geographyConfig: {
                highlightFillColor: '#00f8ff',
                highlightBorderColor: '#000000',
                highlightBorderWidth: 1,
                highlightBorderOpacity: 1,
                popupTemplate: function(geography, data) {
                    return vm.templatePopup({
                        loc: {
                            loc: geography,
                            row: data,
                        },
                    });
                },
            },
            setProjection: function (element) {
                var div = vm.scope === "ind" ? 3 : 4;
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
            locationsService.getLocationByNameAndParent(geography.id, location_id).then(function(locations) {
                var location = locations[0];
                if (!location) {
                    return;
                }
                $location.search('location_name', geography.id);
                $location.search('location_id', location.location_id);
                storageService.setKey('search', $location.search());
            });

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
                    var html = ['<div style="height: 30px !important">', '<div class="row" style="font-size: 15px;">' + this.options.label + '</div>',];
                    for (var fillKey in this.options.fills) {
                        if (fillKey === 'defaultFill') continue;
                        html.push(
                            '<div class="row" style="margin-bottom: 5px;">',
                            '<div class="col-md-1" style="color: '+ this.options.fills[fillKey] +' !important; background-color: ' + this.options.fills[fillKey] + ' !important; width: 30px; height: 30px;"></div>',
                            '<div class="col-md-10">',
                            '<span style="font-size: 15px;">' + fillKey + '</span>',
                            '</div>',
                            '</div>'
                        );
                    }
                    html.push('</div>');
                    d3.select(this.options.element).append('div')
                        .attr('class', 'datamaps-legend')
                        .attr('style', 'width: 300px; left: 1%; bottom: 20%;')
                        .html(html.join(''));
                },
            });
            _.extend(vm.mapPlugins, {
                customTable: function () {
                    if (this.options.rightLegend !== null) {
                        var loc_name = $location.search()['location_name'] || "National";
                        var period = this.options.rightLegend['period'] || 'Monthly';
                        var html = '<div class="map-kpi" style="width: 300px;">';
                        if (this.options.rightLegend['average'] !== void(0)) {
                            html += '<div class="row no-margin">';
                            if (this.options.rightLegend['average_format'] === 'number') {
                                html += '<strong>' + loc_name + ' average:</strong> ' + $filter('indiaNumbers')(this.options.rightLegend['average']);
                            } else {
                                html += '<strong>' + loc_name + ' average:</strong> ' + d3.format('.2f')(this.options.rightLegend['average']) + '%';
                            }
                            html +='</div>';
                            html +='</br>';
                            html += '<div class="row no-margin">';
                            html += this.options.rightLegend['info'];
                            html +='</div>';
                        } else {
                            html += '<div class="row no-margin">';
                            html += this.options.rightLegend['info'];
                            html +='</div>';
                        }
                        html += '</div>';
                        d3.select(this.options.element).append('div')
                            .attr('class', '')
                            .attr('style', 'position: absolute; top: 2%; left: 0; z-index: -1;')
                            .html(html);
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
                            .attr('style', 'position: absolute; width: 100%; top: 5%; right: 25%; z-index: -1;')
                            .html(html.join(''));
                        $compile(ele[0])($scope);
                    }
                },
            });
        }

        $scope.$apply();
    }, 500);

}

IndieMapController.$inject = ['$scope', '$compile', '$location', '$filter', 'storageService', 'locationsService'];

window.angular.module('icdsApp').directive('indieMap', function() {
    return {
        restrict: 'E',
        scope: {
            data: '=?',
            legendTitle: '@?',
            bubbles: '=?',
            templatePopup: '&',
        },
        template: '<div class="indie-map-directive"><datamap on-click="$ctrl.updateMap" map="$ctrl.map" plugins="$ctrl.mapPlugins" plugin-data="$ctrl.mapPluginData"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
