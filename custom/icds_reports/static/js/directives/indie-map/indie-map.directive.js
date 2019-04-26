/* global d3, _, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */

function IndieMapController($scope, $compile, $location, $filter, storageService, locationsService) {
    var vm = this;

    $scope.$watch(function () {
        return vm.data;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        if (newValue.data) {
            vm.map.data = getData(newValue);
        }
        vm.map.fills = newValue.fills;
        vm.map.rightLegend = newValue.rightLegend;
        vm.indicator = newValue.slug;
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

    var location_id = $location.search().location_id;
    vm.type = '';
    vm.mapHeight = 0;

    vm.initTopoJson = function (location_level, location) {
        if (location_level === void(0) || isNaN(location_level) || location_level === -1 || location_level === 4) {
            vm.scope = "ind";
            vm.type = vm.scope + "Topo";
            Datamap.prototype[vm.type] = STATES_TOPOJSON;
        } else if (location_level === 0) {
            vm.scope = location.map_location_name;
            vm.type = vm.scope + "Topo";
            Datamap.prototype[vm.type] = DISTRICT_TOPOJSON;
        } else if (location_level === 1) {
            vm.scope = location.map_location_name;
            vm.type = vm.scope + "Topo";
            Datamap.prototype[vm.type] = BLOCK_TOPOJSON;
        }
        if (Datamap.prototype[vm.type].objects[vm.scope] !== void(0)) {
            if ($location.$$path.indexOf('wasting') !== -1 && location.location_type === 'district') {
                vm.mapHeight = 750;
            } else {
                vm.mapHeight = Datamap.prototype[vm.type].objects[vm.scope].height;
            }
        }
    };

    var mapConfiguration = function (location) {

        var location_level = -1;
        if (location.location_type === 'state') location_level = 0;
        else if (location.location_type === 'district') location_level = 1;
        else if (location.location_type === 'block') location_level = 2;
        else location_level = -1;

        vm.initTopoJson(location_level, location);

        vm.map = {
            scope: vm.scope,
            rightLegend: vm.data && vm.data !== void(0) ? vm.data.rightLegend : null,
            label: vm.data && vm.data !== void(0) ? vm.data.label : null,
            data: getData(vm.data),
            fills: vm.data && vm.data !== void(0) ? vm.data.fills : null,
            height: vm.mapHeight,
            geographyConfig: {
                highlightFillColor: '#00f8ff',
                highlightBorderColor: '#000000',
                highlightBorderWidth: 1,
                highlightBorderOpacity: 1,
                popupTemplate: function (geography, data) {
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

        vm.mapPlugins = {
            bubbles: null,
        };
        vm.mapPluginData = {
            bubbles: [],
        };

        if (vm.map.data) {
            _.extend(vm.mapPlugins, {
                customTable: function () {
                    if (this.options.rightLegend !== null &&
                        d3.select(this.options.element)[0][0].lastChild.className !== 'map-kpi-outer') {
                        var html = [
                            '<div class="map-kpi" style="width: 310px;">',
                            '<div class="row no-margin">',
                            '<div class="row no-margin" style="font-size: 15px;">' + this.options.label + '</div>',
                        ];
                        for (var fillKey in this.options.fills) {
                            if (fillKey === 'defaultFill') continue;
                            html.push(
                                '<div class="row no-margin" style="margin-bottom: 5px;">',
                                '<div class="col-md-1" style="color: ' + this.options.fills[fillKey] + ' !important; background-color: ' + this.options.fills[fillKey] + ' !important; width: 30px; height: 30px;"></div>',
                                '<div class="col-md-10">',
                                '<span style="font-size: 15px;">' + fillKey + '</span>',
                                '</div>',
                                '</div>'
                            );
                        }
                        html.push('<hr/></div>');

                        var locName = 'National';
                        if (storageService.getKey('selectedLocation') !== void(0)) {
                            locName = storageService.getKey('selectedLocation')['name'];
                        }
                        if (this.options.rightLegend['average'] !== void(0)) {
                            html.push('<div class="row no-margin">');
                            if (this.options.rightLegend['average_format'] === 'number') {
                                html.push('<strong>' + locName + ' aggregate (in Month):</strong> ' + $filter('indiaNumbers')(this.options.rightLegend['average']));
                            } else {
                                html.push('<strong>' + locName + ' aggregate (in Month):</strong> ' + d3.format('.2f')(this.options.rightLegend['average']) + '%');
                            }
                            html.push('</div>',
                                '</br>',
                                '<div class="row no-margin">',
                                this.options.rightLegend['info'],
                                '</div>'
                            );
                        } else {
                            html.push(
                                '<div class="row no-margin">',
                                this.options.rightLegend['info'],
                                '</div>'
                            );
                        }
                        if (this.options.rightLegend.extended_info && this.options.rightLegend.extended_info.length > 0) {
                            html.push('<hr/><div class="row  no-margin">');
                            window.angular.forEach(this.options.rightLegend.extended_info, function (info) {
                                html.push(
                                    '<div>' + info.indicator + ' <strong>' + info.value + '</strong></div>'
                                );
                            });
                            html.push('</div>');
                        }

                        html.push('</div>');
                        d3.select(this.options.element).append('div')
                            .attr('class', 'map-kpi-outer')
                            .attr('style', 'position: absolute; top: 15px; left: 0; z-index: -1')
                            .html(html.join(''));
                        var mapHeight = d3.select(this.options.element)[0][0].offsetHeight;
                        var legendHeight = d3.select(this.options.element)[0][0].lastElementChild.offsetHeight;
                        if (mapHeight < legendHeight + 15) {
                            d3.select(this.options.element)[0][0].style.height = legendHeight + 15 + "px";
                        }
                    }
                },
            });
        }
    };

    locationsService.getLocation(location_id).then(function (location) {
        mapConfiguration(location);
    });

    vm.indicator = vm.data && vm.data !== void(0) ? vm.data.slug : null;

    vm.changeIndicator = function (value) {
        window.angular.forEach(vm.data, function (row) {
            if (row.slug === value) {
                vm.map.data = row.data;
                vm.map.fills = row.fills;
                vm.map.rightLegend = row.rightLegend;
            }
        });
        vm.indicator = value;
    };

    var getData = function (data) {
        var mapData = data && data !== void(0) ? data.data : null;
        if (!mapData) {
            return null;
        }
        return mapData;
    };

    vm.getHtmlContent = function (geography) {
        var html = "";
        html += "<div class=\"modal-header\">";
        html += '<button type="button" class="close" ng-click="$ctrl.closePopup()" ' +
                'aria-label="Close"><span aria-hidden="true">&times;</span></button>';
        html += "</div>";
        html +="<div class=\"modal-body\">";
        window.angular.forEach(vm.data.data[geography.id].original_name, function (value) {
            html += '<button class="btn btn-xs btn-default" ng-click="$ctrl.updateMap(\'' + value + '\')">' + value + '</button>';
        });
        html += "</div>";
        return html;
    };

    vm.closePopup = function () {
        var popup = d3.select("#locPopup");
        popup.classed("hidden", true);
    };

    vm.updateMap = function (geography) {
        if (geography.id !== void(0) && vm.data.data[geography.id] && vm.data.data[geography.id].original_name.length > 1) {
            var html = vm.getHtmlContent(geography);
            var css = 'display: block; left: ' + event.layerX + 'px; top: ' + event.layerY + 'px;';

            var popup = d3.select('#locPopup');
            popup.classed("hidden", false);
            popup.attr('style', css)
                .html(html);

            $compile(popup[0])($scope);
        } else {
            var location = geography.id || geography;
            if (geography.id !== void(0) && vm.data.data[geography.id] && vm.data.data[geography.id].original_name.length === 1) {
                location = vm.data.data[geography.id].original_name[0];
            }
            locationsService.getLocationByNameAndParent(location, location_id).then(function (locations) {
                var location = locations[0];
                if (!location) {
                    return;
                }
                $location.search('location_name', (geography.id || geography));
                $location.search('location_id', location.location_id);
                storageService.setKey('search', $location.search());
            });
        }

    };

}

IndieMapController.$inject = ['$scope', '$compile', '$location', '$filter', 'storageService', 'locationsService'];

window.angular.module('icdsApp').directive('indieMap', function () {
    return {
        restrict: 'E',
        scope: {
            data: '=?',
            legendTitle: '@?',
            bubbles: '=?',
            templatePopup: '&',
        },
        template: '<div class="indie-map-directive"><div id="locPopup" class="locPopup"></div><datamap on-click="$ctrl.updateMap" map="$ctrl.map" plugins="$ctrl.mapPlugins" plugin-data="$ctrl.mapPluginData"></datamap></div>',
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
});
