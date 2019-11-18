/* global d3, moment */

window.angular.module('icdsApp').factory('baseControllersService', function() {
    return {
        BaseController: function ($scope, $routeParams, $location, locationsService, userLocationId,
            storageService, haveAccessToAllLocations, haveAccessToFeatures) {
            var vm = this;
            if (Object.keys($location.search()).length === 0) {
                $location.search(storageService.getKey('search'));
            } else {
                storageService.setKey('search', $location.search());
            }

            vm.userLocationId = userLocationId;
            vm.filtersData = $location.search();
            vm.step = $routeParams.step;
            vm.chartData = null;
            vm.top_five = [];
            vm.bottom_five = [];
            vm.selectedLocations = [];
            vm.all_locations = [];
            vm.location_type = null;
            vm.loaded = false;

            vm.haveAccessToFeatures = haveAccessToFeatures;
            vm.message = storageService.getKey('message') || false;

            $scope.$watch(function() {
                return vm.selectedLocations;
            }, function (newValue, oldValue) {
                if (newValue === oldValue || !newValue || newValue.length === 0) {
                    return;
                }
                if (newValue.length === 6) {
                    var parent = newValue[3];
                    $location.search('location_id', parent.location_id);
                    $location.search('selectedLocationLevel', 3);
                    $location.search('location_name', parent.name);
                    storageService.setKey('message', true);
                    setTimeout(function() {
                        storageService.setKey('message', false);
                    }, 3000);
                }
                return newValue;
            }, true);

            vm.createTemplatePopup = function(header, lines) {
                var template = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
                    '<p>' + header + '</p>';
                for (var i = 0; i < lines.length; i++) {
                    template += '<div>' + lines[i]['indicator_name'] + '<strong>' + lines[i]['indicator_value'] + '</strong></div>';
                }
                template += '</div>';
                return template;
            };
            vm.getLocationType = function() {
                if (vm.location) {
                    if (vm.location.location_type === 'supervisor') {
                        return "Sector";
                    } else {
                        return vm.location.location_type.charAt(0).toUpperCase() +
                            vm.location.location_type.slice(1);
                    }
                }
                return 'National';
            };
            vm.setStepsMapLabel = function() {
                var locType = vm.getLocationType();
                if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
                    vm.mode = 'sector';
                    vm.steps['map'].label = locType + ' View';
                } else {
                    vm.mode = 'map';
                    vm.steps['map'].label = 'Map View: ' + locType;
                }
            };
            vm.loadDataFromResponse = function(usePercentage, forceYAxisFromZero) {
                var tailsMultiplier = 1;
                if (usePercentage) {
                    tailsMultiplier = 100;
                }
                var parseTails = function(value) {
                    var precision = 0;
                    if (usePercentage) {
                        precision = 2;
                    }
                    return parseFloat((value / tailsMultiplier).toFixed(precision));
                };
                return function(response) {
                    if (vm.step === "map") {
                        vm.data.mapData = response.data.report_data;
                    } else if (vm.step === "chart") {
                        vm.chartData = response.data.report_data.chart_data;
                        vm.all_locations = response.data.report_data.all_locations;
                        vm.top_five = response.data.report_data.top_five;
                        vm.bottom_five = response.data.report_data.bottom_five;
                        vm.location_type = response.data.report_data.location_type;
                        vm.chartTicks = vm.chartData[0].values.map(function (d) { return d.x; });
                        var max = Math.ceil(d3.max(vm.chartData, function (line) {
                            return d3.max(line.values, function (d) {
                                return d.y;
                            });
                        }) * tailsMultiplier);
                        var min = Math.ceil(d3.min(vm.chartData, function (line) {
                            return d3.min(line.values, function (d) {
                                return d.y;
                            });
                        }) * tailsMultiplier);
                        var range = max - min;
                        vm.chartOptions.chart.forceY = [
                            ((min - range / 10) < 0 || forceYAxisFromZero) ? 0 : parseTails(min - range / 10),
                            parseTails(max + range / 10),
                        ];
                    }
                };
            };
            vm.init = function() {
                var locationId = vm.filtersData.location_id || vm.userLocationId;
                if (!locationId || ["all", "null", "undefined"].indexOf(locationId) >= 0) {
                    vm.loadData();
                    vm.loaded = true;
                    return;
                }
                locationsService.getLocation(locationId).then(function(location) {
                    vm.location = location;
                    vm.loadData();
                    vm.loaded = true;
                });
            };
            $scope.$on('filtersChange', function() {
                vm.loadData();
            });
            vm.getDisableIndex = function () {
                var i = -1;
                if (!haveAccessToAllLocations) {
                    window.angular.forEach(vm.selectedLocations, function (key, value) {
                        if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                            i = value;
                        }
                    });
                }
                return i;
            };
            vm.moveToLocation = function(loc, index) {
                if (loc === 'national') {
                    $location.search('location_id', '');
                    $location.search('selectedLocationLevel', -1);
                    $location.search('location_name', '');
                } else {
                    $location.search('location_id', loc.location_id);
                    $location.search('selectedLocationLevel', index);
                    $location.search('location_name', loc.name);
                }
            };
            vm.getChartOptions = function(options) {
                return {
                    chart: {
                        type: 'lineChart',
                        height: 450,
                        margin : {
                            top: 20,
                            right: 60,
                            bottom: 60,
                            left: 80,
                        },
                        x: function(d){ return d.x; },
                        y: function(d){ return d.y; },
                        useInteractiveGuideline: true,
                        clipVoronoi: false,
                        tooltips: true,
                        xAxis: {
                            axisLabel: '',
                            showMaxMin: true,
                            tickFormat: function(d) {
                                return d3.time.format(options['xAxisTickFormat'])(new Date(d));
                            },
                            tickValues: function() {
                                return vm.chartTicks;
                            },
                            axisLabelDistance: -100,
                        },

                        yAxis: {
                            axisLabel: '',
                            tickFormat: function(d){
                                return d3.format(options['yAxisTickFormat'])(d);
                            },
                            axisLabelDistance: 20,
                            forceY: [0],
                        },
                        callback: function(chart) {
                            var tooltip = chart.interactiveLayer.tooltip;
                            tooltip.contentGenerator(function (d) {
                                var day = _.find(vm.chartData[0].values, function(num) {
                                    return num['x'] === d.value;
                                });
                                return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), day);
                            });
                            return chart;
                        },
                    },
                    caption: {
                        enable: true,
                        html: '<i class="fa fa-info-circle"></i>' + options['captionContent'],
                        css: {
                            'text-align': 'center',
                            'margin': '0 auto',
                            'width': '900px',
                        },
                    },
                };
            };
            vm.createTooltipContent = function(header, lines) {
                var template = "<p><strong>" + header + "</strong></p><br/>";
                for (var i = 0; i < lines.length; i++) {
                    template += '<div>' + lines[i]['indicator_name'] + '<strong>' + lines[i]['indicator_value'] + '</strong></div>';
                }
                return template;
            };
        },
    };
});
