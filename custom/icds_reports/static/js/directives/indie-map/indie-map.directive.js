/* global d3, _, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */

function IndieMapController($scope, $compile, $location, $filter, storageService, locationsService,
    topojsonService, haveAccessToFeatures, isMobile) {
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

    vm.initTopoJson = function (locationLevel, location, topojson) {
        if (locationLevel === void(0) || isNaN(locationLevel) || locationLevel === -1 || locationLevel === 4) {
            vm.scope = "ind";
            vm.type = vm.scope + "Topo";
            vm.rawTopojson = topojson;
        } else if (locationLevel === 0) {
            vm.scope = location.map_location_name;
            vm.type = vm.scope + "Topo";
            vm.rawTopojson = topojson;
        } else if (locationLevel === 1) {
            vm.scope = location.map_location_name;
            vm.type = vm.scope + "Topo";
            vm.rawTopojson = topojson;
        }
        if (vm.rawTopojson && vm.rawTopojson.objects[vm.scope] !== void(0)) {
            Datamap.prototype[vm.type] = vm.rawTopojson;
            if ($location.$$path.indexOf('wasting') !== -1 && location.location_type === 'district') {
                vm.mapHeight = 750;
            } else {
                vm.mapHeight = vm.rawTopojson.objects[vm.scope].height;
            }
            if (isMobile) {
                // scale maps based on space available on device.
                var headerHeight = $('#map-chart-header').height() + $('#page-heading').innerHeight();
                var legendHeight = 145; // fixed legend height to calculate available space for map
                // always set map height to available height, which is:
                // widow height - height of the header - legend height - 44px of additional padding / margins
                vm.mapHeight = window.innerHeight - headerHeight - legendHeight - 44;
            }
        }
    };

    // this function was copied with minor modification (inputs and variable names) from
    // https://data-map-d3.readthedocs.io/en/latest/steps/step_03.html
    function calculateScaleCenter(path, features, width, height) {
        // Get the bounding box of the paths (in pixels!) and calculate a
        // scale factor based on the size of the bounding box and the map
        // size.
        var bboxPath = path.bounds(features),
            scale = 0.95 / Math.max(
                (bboxPath[1][0] - bboxPath[0][0]) / width,
                (bboxPath[1][1] - bboxPath[0][1]) / height
            );

        // Get the bounding box of the features (in map units!) and use it
        // to calculate the center of the features.
        var bboxFeature = d3.geo.bounds(features),
            center = [
                (bboxFeature[1][0] + bboxFeature[0][0]) / 2,
                (bboxFeature[1][1] + bboxFeature[0][1]) / 2];

        if (!isMobile) {
            // for web maps, downsize the scale a bit to avoid overwriting the legend
            scale = scale * .75;
        }
        return {
            'scale': scale,
            'center': center,
        };
    }

    function getLocationLevelFromType(locationType) {
        if (locationType === 'state') {
            return 0;
        } else if (locationType === 'district') {
            return 1;
        } else if (locationType === 'block') {
            return 2;
        } else {
            return -1;
        }
    }

    function getPopupForGeography(geography) {
        return vm.templatePopup({
            loc: {
                loc: geography,
                row: vm.map.data[geography.id],
            },
        });
    }

    var mapConfiguration = function (location, topojson) {
        var locationLevel = getLocationLevelFromType(location.location_type);
        vm.initTopoJson(locationLevel, location, topojson);
        vm.map = {
            scope: vm.scope,
            rightLegend: vm.data && vm.data !== void(0) ? vm.data.rightLegend : null,
            label: vm.data && vm.data !== void(0) ? vm.data.label : null,
            data: getData(vm.data),
            fills: vm.data && vm.data !== void(0) ? vm.data.fills : null,
            height: vm.mapHeight,
            geographyConfig: {
                popupOnHover: !isMobile,
                highlightFillColor: '#00f8ff',
                highlightBorderColor: '#000000',
                highlightBorderWidth: 1,
                highlightBorderOpacity: 1,
                popupTemplate: function (geography, data) {
                    return getPopupForGeography(geography);
                },
            },
            setProjection: function (element) {
                var div = vm.scope === "ind" ? 3 : 4;
                var options = vm.rawTopojson.objects[vm.scope];
                var projection, path;
                if (isMobile || !options.center) {
                    // load a dummy projection so we can calculate the true size
                    // more here: https://data-map-d3.readthedocs.io/en/latest/steps/step_03.html#step-03
                    projection = d3.geo.equirectangular().scale(1);
                    path = d3.geo.path().projection(projection);
                    var feature = window.topojson.feature(vm.rawTopojson, options);
                    var scaleCenter = calculateScaleCenter(
                        path, feature,
                        element.offsetWidth, element.offsetHeight
                    );
                    projection.scale(scaleCenter.scale)
                        .center(scaleCenter.center)
                        .translate([element.offsetWidth / 2, element.offsetHeight / 2]); // sets map in center of canvas

                    if (isMobile) {
                        // setting zoom out limit
                        // references: https://data-map-d3.readthedocs.io/en/latest/steps/step_06.html#step-06
                        $(function () {
                            // DOM Ready
                            var svg = d3.select('#map svg'); //selects svg in datamap component
                            var zoom = d3.behavior.zoom().scaleExtent([1, 10]).on('zoom', function () {
                                // this function redraws the map rendered on zoom event
                                // reference: node_modules/angular-datamaps/dist/angular-datamaps.js (line 27)
                                svg.selectAll('g').attr("transform",
                                    "translate(" + d3.event.translate + ") scale(" + d3.event.scale + ")");
                            });
                            svg.call(zoom); //connects zoom event to map
                            // overrides default overflow value (hidden) of svg, which allows map to zoom over legend
                            svg.style("overflow", "inherit");
                        });
                    }

                } else {
                    projection = d3.geo.equirectangular()
                        .center(options.center)
                        .scale(options.scale)
                        .translate([element.offsetWidth / 2, element.offsetHeight / div]);
                    path = d3.geo.path().projection(projection);
                }
                $(function () {
                    // this function runs after the dom (map) is rendered.
                    // Datamaps take "id" of a location and assign it as class in the canvas path element.
                    // In certain cases where there is a space in the "id" of a location it will be added as multiple
                    // classes to the path element. When map is being colored, it looks for path elements which has the
                    // class same as the id. (for reference check line 1128 of this library file: datamaps.js).
                    // But, since there is a space in "id", it looks for path element which has only the first part of
                    // "id" as its class (this class name could conflict with other locations). So, we are explicitly
                    // adding a class with all the spaces and special characters removed from "id" to uniquely
                    // differentiate it from other locations before filling the colors.
                    var svg = d3.select('#map svg');
                    svg.selectAll(".datamaps-subunit").transition().style('fill', vm.map.fills.defaultFill);
                    vm.addCombinedSelectorClassToMaps(document.getElementsByClassName("datamaps-subunit"));
                    vm.colorMapBasedOnCombinedSelectorClass(svg);
                });
                return {path: path, projection: projection};
            },
        };
        if (isMobile) {
            // this is used to add padding in datamap that we don't want on mobile.
            // can't set to 0 because then it will default to 50
            vm.map.options = {
                legendHeight: 1,
            };
        }

        vm.addCombinedSelectorClassToMaps = function (locations) {
            for (var i = 0; i < locations.length; i++) {
                var combinedClass = "";
                for (var j = 0; j < locations[i].classList.length; j++) {
                    // removing all the special characters in strings before creating combined class
                    // Reference: https://stackoverflow.com/a/6555220/12839195
                    combinedClass += locations[i].classList[j].replace(/[^a-zA-Z0-9]/g, "");
                }
                locations[i].classList.add(combinedClass);
            }
        };
        vm.colorMapBasedOnCombinedSelectorClass = function (svg) {
            for (var locationId in vm.map.data) {
                if (vm.map.data.hasOwnProperty(locationId)) {
                    // removing all the special characters in locationId before checking for combined class
                    // Reference: https://stackoverflow.com/a/6555220/12839195
                    svg.selectAll('.datamapssubunit' + locationId.replace(/[^a-zA-Z0-9]/g, ""))
                        .transition().style('fill', vm.map.data[locationId].fillKey);
                }
            }
        };
        vm.mapPlugins = {
            bubbles: null,
        };
        vm.mapPluginData = {
            bubbles: [],
        };

        if (vm.map.data) {
            // this chunk of code adds the legend
            _.extend(vm.mapPlugins, {
                customTable: function () {
                    if (this.options.rightLegend !== null &&
                        d3.select(this.options.element)[0][0].lastChild.className !== 'map-kpi-outer') {
                        var html = [
                            '<div class="map-kpi">',
                            '<div class="row no-margin">',
                            '<div class="row no-margin map-legend-title"">' + this.options.label + '</div>',
                        ];
                        for (var fillKey in this.options.fills) {
                            if (fillKey === 'defaultFill') {
                                continue;
                            }
                            html.push(
                                '<div class="row no-margin map-legend-color-row">',
                                '<div class="col-xs-1 map-legend-color" style="color: ' + this.options.fills[fillKey] + ' !important; background-color: ' + this.options.fills[fillKey] + ' !important;"></div>',
                                '<div class="col-xs-10 map-legend-color-label">' + fillKey + '</div>',
                                '</div>'
                            );
                        }
                        if (!isMobile) {
                            // only add the last two sections to web-based legend
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
                        }

                        d3.select(this.options.element).append('div')
                            .attr('class', 'map-kpi-outer')
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
        var locationLevel = getLocationLevelFromType(location.location_type);
        if (locationLevel === -1) {
            topojsonService.getStateTopoJson().then(function (resp) {
                mapConfiguration(location, resp);
            });
        } else if (locationLevel === 0) {
            topojsonService.getDistrictTopoJson().then(function (resp) {
                mapConfiguration(location, resp);
            });
        } else if (locationLevel === 1) {
            topojsonService.getBlockTopoJsonForState(location.parent_map_name).then(
                function (resp) {
                    mapConfiguration(location, resp.topojson);
                }
            );
        } else {
            mapConfiguration(location);
        }
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

    vm.getSecondaryLocationSelectionHtml = function (geography) {
        var html = "";
        html += '<div class="secondary-location-selector">';
        html += '<div class="modal-header">';
        html += '<button type="button" class="close" ng-click="$ctrl.closePopup($event)" aria-label="Close">' +
            '<span aria-hidden="true">&times;</span></button>';
        html += "</div>";
        html += '<div class="modal-body">';
        window.angular.forEach(vm.data.data[geography.id].original_name, function (value) {
            html += '<button class="btn btn-xs btn-default" ng-click="$ctrl.attemptToDrillToLocation(\'' + value + '\')">' + value + '</button>';
        });
        html += "</div>";
        html += "</div>";
        return html;
    };

    vm.closePopup = function (e) {
        // checking if click event is triggered on map
        if (e.target.tagName !== 'path') {
            var popup = d3.select("#locPopup");
            popup.classed("hidden", true);
        }
    };

    function renderPopup(html) {
        return vm.renderPopup(html, 'locPopup');
    }

    vm.renderPopup = function (html, divId) {
        var css = 'display: block; left: ' + event.layerX + 'px; top: ' + event.layerY + 'px;';
        var popup = d3.select('#' + divId);
        popup.classed("hidden", false);
        popup.attr('style', css).html(html);
        $compile(popup[0])($scope);
    };

    function showSecondaryLocationSelectionPopup(geography) {
        var html = vm.getSecondaryLocationSelectionHtml(geography);
        renderPopup(html);
    }

    function getLocationNameFromGeography(geography) {
        var location = geography.id || geography;
        if (geography.id !== void(0) && vm.data.data[geography.id] && vm.data.data[geography.id].original_name.length === 1) {
            location = vm.data.data[geography.id].original_name[0];
        }
        return location;
    }

    vm.attemptToDrillToLocation = function (geography) {
        var location = getLocationNameFromGeography(geography);
        locationsService.tryToNavigateToLocation(location, location_id);
    };

    vm.handleMobileDrilldown = function () {
        vm.handleDrillDownClick(vm.selectedGeography);
    };

    vm.handleDrillDownClick = function (geography) {
        if (geography.id !== void(0) && vm.data.data[geography.id] && vm.data.data[geography.id].original_name.length > 1) {
            showSecondaryLocationSelectionPopup(geography);
        } else {
            vm.attemptToDrillToLocation(geography);
        }
    };

    vm.handleMapClick = function (geography) {
        if (isMobile) {
            vm.selectedGeography = geography;
            var popupHtml = getPopupForGeography(geography);
            renderPopup(popupHtml);
        } else {
            vm.handleDrillDownClick(geography);
        }
    };

}

IndieMapController.$inject = [
    '$scope', '$compile', '$location', '$filter', 'storageService', 'locationsService', 'topojsonService',
    'haveAccessToFeatures', 'isMobile',
];

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').directive('indieMap', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        scope: {
            data: '=?',
            legendTitle: '@?',
            bubbles: '=?',
            templatePopup: '&',
        },
        templateUrl: templateProviderService.getTemplate('indie-map.directive'),
        bindToController: true,
        controller: IndieMapController,
        controllerAs: '$ctrl',
    };
}]);
