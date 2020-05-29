/* global d3, moment */

window.angular.module('icdsApp').factory('baseControllersService', ['$timeout', function ($timeout) {
    var BaseFilterController = function ($scope, $routeParams, $location, dateHelperService, storageService,
        navigationService) {
        var vm = this;
        vm.moveToLocation = function (loc, index) {
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
        vm.addAdditionalFilters = function (gender, age) {
            $location.search('gender', gender);
            $location.search('age', age);
        };
        vm.selectedLocationsCount = function () {
            // this method returns selectedLocationLevel
            // TODO: Need to check why selectedLocationLevel is undefined for all location levels except when awc is selected
            // when awc is selected return selected location level as is or count non null elements in selected Locations array
            // selectedLocations array is fixed array of size 5. default value: [all, null,null,null,null]
            // vm.selectedLocations.filter(Boolean) returns array after removing all null entries
            // eg: if block is selected selectedLocations is (state, district, block, all, null)- only 3 levels selected.
            // since 3 levels are selected, selectedLocationLevel is 2 and vm.selectedLocations.filter(Boolean) = 4
            return vm.selectedLocationLevel ? vm.selectedLocationLevel : (vm.selectedLocations.filter(Boolean).length - 2);
        };
        vm.filtersOpen = false;
        $scope.$on('openFilterMenu', function () {
            vm.filtersOpen = true;
        });
        $scope.$on('closeFilterMenu', function () {
            vm.filtersOpen = false;
        });
        $scope.$on('mobile_filter_data_changed', function (event, data) {
            vm.filtersOpen = false;
            if (!data.location) {
                vm.moveToLocation('national', -1);

            } else {
                vm.moveToLocation(data.location, data.locationLevel);
            }
            if (data.locationLevel === 4 && $location.path().indexOf('awc_reports') === -1) {
                // jump to AWC reports if an AWC is selected
                $location.path(navigationService.getAWCTabFromPagePath($location.path()));
            }
            dateHelperService.updateSelectedMonth(data['month'], data['year']);
            vm.addAdditionalFilters(data.gender, data.age);
            storageService.setKey('search', $location.search());
            $scope.$emit('filtersChange');
        });
        vm.selectedMonthDisplay = dateHelperService.getSelectedMonthDisplay();
        vm.selectedLocation = function () {
            return storageService.getKey('selectedLocation');
        };
        vm.selectedDate = dateHelperService.getSelectedDate();
        vm.showReassignmentMessage = function () {
            var utcSelectedDate = Date.UTC(vm.selectedDate.getFullYear(), vm.selectedDate.getMonth());
            return vm.selectedLocation() && (Date.parse(vm.selectedLocation().archived_on) <= utcSelectedDate || Date.parse(vm.selectedLocation().deprecates_at) > utcSelectedDate);
        };
    };
    return {
        BaseController: function ($scope, $routeParams, $location, locationsService, dateHelperService,
            navigationService, userLocationId, storageService, haveAccessToAllLocations, haveAccessToFeatures,
            isMobile) {
            BaseFilterController.call(
                this, $scope, $routeParams, $location, dateHelperService, storageService, navigationService
            );
            var vm = this;

            if (Object.keys($location.search()).length === 0) {
                $location.search(storageService.getKey('search'));
            } else {
                storageService.setKey('search', $location.search());
            }
            vm.userLocationId = userLocationId;
            vm.filtersData = $location.search();
            vm.step = $routeParams.step;
            vm.haveAccessToAllLocations = haveAccessToAllLocations;
            vm.chartData = null;
            vm.top_five = [];
            vm.bottom_five = [];
            vm.selectedLocations = [];
            vm.all_locations = [];
            vm.location_type = null;
            vm.loaded = false;

            vm.haveAccessToFeatures = haveAccessToFeatures;
            vm.message = storageService.getKey('message') || false;

            // variables used for chart rendering. can be overridden by subclasses
            vm.usePercentage = true;
            vm.forceYAxisFromZero = false;

            $scope.$watch(function () {
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
                    setTimeout(function () {
                        storageService.setKey('message', false);
                    }, 3000);
                }
                return newValue;
            }, true);

            vm.getSteps = function (baseRoute) {
                return {
                    'map': {route: baseRoute + 'map', label: 'Map View'},
                    'chart': {route: baseRoute + 'chart', label: isMobile ? 'Rankings' : 'Chart View'},
                };
            };

            vm.getPopupSubheading = function () {
                // if the map popup should have a subheading, then implement this function in a subclass
                // this is inserted before the indicators. see `AWCSCoveredController` for an example usage.
                return '';
            };

            vm.templatePopup = function (loc, row) {
                // subclasses that don't override this must implement vm.getPopupData
                // See UnderweightChildrenReportController for an example
                var popupData = vm.getPopupData(row);
                return vm.createMapPopupTemplate(
                    loc.properties.name,
                    popupData,
                    vm.getPopupSubheading()
                );
            };

            vm.createMapPopupTemplate = function (locationName, lines, subheading) {
                var template = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
                    '<p>' + locationName + '</p>';
                if (subheading) {
                    template += '<p>' + subheading + '</p>';
                }
                for (var i = 0; i < lines.length; i++) {
                    template += '<div>' + lines[i]['indicator_name'] + '<strong>' + lines[i]['indicator_value'] + '</strong></div>';
                }
                if (isMobile) {
                    // assume called in the context of either indie-map or map-or-sector-view,
                    // which both have this function.
                    template += '<a ng-click="$ctrl.handleMobileDrilldown()">see more</a>';
                }
                template += '</div>';
                return template;
            };

            vm.getLocationType = function () {
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
            vm.setStepsMapLabel = function () {
                var locType = vm.getLocationType();
                if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
                    vm.mode = 'sector';
                    vm.steps['map'].label = locType + ' View';
                } else {
                    vm.mode = 'map';
                    vm.steps['map'].label = 'Map View: ' + locType;
                }
            };
            vm.loadDataFromResponse = function (usePercentage, forceYAxisFromZero, overrideStep) {
                // if overrideStep is defined use it, else just use the current step
                // mobile dashboard requires this to load data beyond the currently displayed step on some pages
                var currentStep = overrideStep || vm.step;
                var tailsMultiplier = 1;
                if (usePercentage) {
                    tailsMultiplier = 100;
                }
                var parseTails = function (value) {
                    var precision = 0;
                    if (usePercentage) {
                        precision = 2;
                    }
                    return parseFloat((value / tailsMultiplier).toFixed(precision));
                };
                return function (response) {
                    if (currentStep === "map") {
                        vm.data.mapData = response.data.report_data;
                    } else if (currentStep === "chart") {
                        vm.chartData = response.data.report_data.chart_data;
                        vm.all_locations = response.data.report_data.all_locations;
                        vm.top_five = response.data.report_data.top_five;
                        vm.bottom_five = response.data.report_data.bottom_five;
                        vm.location_type = response.data.report_data.location_type;
                        vm.chartTicks = vm.chartData[0].values.map(function (d) {
                            return d.x; 
                        });
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

            vm.loadData = function () {
                // a default implementation of loadData that is web and mobile friendly.
                // subclasses that don't override this must set vm.serviceDataFunction to a function
                // that takes in the current step and filters and returns the appropriate data from the relevant
                // service. See UnderweightChildrenReportController for an example
                vm.setStepsMapLabel();
                // mobile dashboard requires map data on the chart pages, whereas web just requires the current
                // step's data.
                // note: it would be better to not load this data on both step pages but instead save it in the
                // JS, but doing that now would be a bit complicated and the server-side caching should make the
                // switching relatively painless
                var allSteps = (isMobile && vm.step === 'chart') ? ['map', 'chart'] : [vm.step];
                for (var i = 0; i < allSteps.length; i++) {
                    var currentStep = allSteps[i];
                    vm.myPromise = vm.serviceDataFunction(currentStep, vm.filtersData).then(
                        vm.loadDataFromResponse(vm.usePercentage, vm.forceYAxisFromZero, currentStep)
                    );
                }
            };

            //Creating a promise, which resolves only after map is rendered (wait until canvas is rendered in dom)
            // Reference: https://stackoverflow.com/a/47776379/12839195 (using timeout instead of rafAsync)
            vm.waitForMapIfNecessary = function () {
                // if it is not a page where map is displayed, resolve the promise immediately,
                // else wait till canvas (svg in dom) is created
                if (!navigationService.isMapDisplayed($location.path()) && window.Promise) {
                    return window.Promise.resolve(true);
                }
                if (document.querySelector('svg') === null) {
                    return $timeout().then(function () {
                        return vm.waitForMapIfNecessary();
                    });
                } else {
                    return window.Promise.resolve(true);
                }
            };

            vm.mapLoadingPromise = vm.waitForMapIfNecessary().then(function () {
            });

            vm.init = function () {
                var locationId = vm.filtersData.location_id || vm.userLocationId;
                if (!locationId || ["all", "null", "undefined"].indexOf(locationId) >= 0) {
                    vm.loadData();
                    vm.loaded = true;
                    return;
                }
                locationsService.getLocation(locationId).then(function (location) {
                    vm.location = location;
                    vm.loadData();
                    vm.loaded = true;
                });
            };
            $scope.$on('filtersChange', function () {
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

            // reduce caption width to fit screen up to 900px on mobile view
            var captionWidth = (isMobile && window.innerWidth < 960) ? window.innerWidth - 60 : 900;

            vm.getChartOptions = function (options) {
                return {
                    chart: {
                        type: 'lineChart',
                        height: 450,
                        margin: {
                            top: 20,
                            right: 60,
                            bottom: 60,
                            left: isMobile ? 50 : 80,
                        },
                        x: function (d) {
                            return d.x; 
                        },
                        y: function (d) {
                            return d.y; 
                        },
                        useInteractiveGuideline: true,
                        clipVoronoi: false,
                        tooltips: true,
                        xAxis: {
                            axisLabel: '',
                            showMaxMin: true,
                            tickFormat: function (d) {
                                return d3.time.format(options['xAxisTickFormat'])(new Date(d));
                            },
                            tickValues: function () {
                                return vm.chartTicks;
                            },
                            axisLabelDistance: -100,
                        },

                        yAxis: {
                            axisLabel: '',
                            tickFormat: function (d) {
                                return d3.format(options['yAxisTickFormat'])(d);
                            },
                            axisLabelDistance: 20,
                            forceY: [0],
                        },
                        callback: function (chart) {
                            var tooltip = chart.interactiveLayer.tooltip;
                            tooltip.contentGenerator(function (d) {
                                var day = _.find(vm.chartData[0].values, function (num) {
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
                            'width': captionWidth + 'px',
                        },
                    },
                };
            };
            vm.createTooltipContent = function (header, lines) {
                var template = "<p><strong>" + header + "</strong></p><br/>";
                for (var i = 0; i < lines.length; i++) {
                    template += '<div>' + lines[i]['indicator_name'] + '<strong>' + lines[i]['indicator_value'] + '</strong></div>';
                }
                return template;
            };

            // mobile dashboard
            // subsection navigation support
            vm.goToRoute = function (route) {
                $location.path(route);
            };
            // month filter support
            vm.selectedMonthDisplay = dateHelperService.getSelectedMonthDisplay();

            // popup support on rankings pages
            vm.displayMobilePopup = function (location) {
                // data is stored in .data for the first three location levels, but then moves to tooltips_data
                var dataSource = vm.data.mapData.data || vm.data.mapData.tooltips_data;
                var locationData = dataSource[location.loc_name];
                var data = vm.getPopupData(locationData);
                vm.mobilePopupLocation = location;
                vm.mobilePopupData = data;
            };
            vm.drilldownToLocationWithName = function (locationName) {
                // todo: this is heavily copied from map-or-sector-view's handling of the map click event
                // but there's not a great place to share the code since they're managed by separate controllers
                var currentLocationId = $location.search().location_id;
                locationsService.getLocationByNameAndParent(locationName, currentLocationId).then(function (locations) {
                    var location = locations[0];
                    $location.search('location_name', location.name);
                    $location.search('location_id', location.location_id);

                    storageService.setKey('search', $location.search());
                    if (location.location_type_name === 'awc') {
                        $location.path(navigationService.getAWCTabFromPagePath($location.path()));
                    }
                });
            };
        },
        BaseFilterController: BaseFilterController,
    };
}]);
