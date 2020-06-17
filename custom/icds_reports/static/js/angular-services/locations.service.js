window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', 'storageService', 'navigationService', function ($http, $location, storageService, navigationService) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    var ALL_OPTION =  {
        name: 'All',
        location_id: 'all',
        user_have_access: 0,
        user_have_access_to_parent: 1,
    };
    var NATIONAL_OPTION = {name: 'National', location_id: 'all'};
    var sector_level = 4;

    function transformLocationTypeName(locationTypeName) {
        if (locationTypeName === 'awc') {
            return locationTypeName.toUpperCase();
        } else if (locationTypeName === 'supervisor') {
            return 'Sector';
        } else {
            return locationTypeName.charAt(0).toUpperCase() + locationTypeName.slice(1);
        }
    }

    function getLocationByNameAndParent(name, parentId) {
        var includeTest = $location.search()['include_test'];
        gtag.event('Location Service', 'Fetching data started', 'getLocationByNameAndParent');
        return $http.get(url('icds_locations'), {
            params: {name: name, parent_id: parentId, include_test: includeTest},
        }).then(
            function (response) {
                gtag.event('Location Service', 'Fetching data succeeded', 'getLocationByNameAndParent');
                return response.data.locations;
            },
            function () {
                gtag.event('Location Service', 'Fetching data failed', 'getLocationByNameAndParent');
            }
        );
    }
    function tryToNavigateToLocation(locationName, parentLocationId) {
        getLocationByNameAndParent(locationName, parentLocationId).then(function (locations) {
            if (locations.length > 0) {
                var location = locations[0];
                $location.search('location_name', location.name);
                $location.search('location_id', location.location_id);
                storageService.setKey('search', $location.search());
                if (location.location_type_name === 'awc') {
                    $location.path(navigationService.getAWCTabFromPagePath($location.path()));
                }
            }
        });
    }

    return {
        ALL_OPTION: ALL_OPTION,
        NATIONAL_OPTION: NATIONAL_OPTION,
        getRootLocations: function () {
            return this.getChildren(null);
        },
        getChildren: function (parentId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getChildren');
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId, include_test: includeTest},
            }).then(
                function (response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getChildren');
                    return response.data;
                },
                function () {
                    gtag.event('Location Service', 'Fetching data failed', 'getChildren');
                }
            );
        },
        getAncestors: function (locationId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getAncestors');
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function (response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getAncestors');
                    return response.data;
                },
                function () {
                    gtag.event('Location Service', 'Fetching data failed', 'getAncestors');
                }
            );
        },
        getLocation: function (locationId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getLocation');
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function (response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getLocation');
                    return response.data;
                },
                function () {
                    gtag.event('Location Service', 'Fetching data failed', 'getLocation');
                }
            );
        },
        getLocationByNameAndParent: getLocationByNameAndParent,
        tryToNavigateToLocation: tryToNavigateToLocation,
        getAwcLocations: function (locationId) {
            gtag.event('Location Service', 'Fetching data started', 'getAwcLocations');
            return $http.get(url('awc_locations'), {
                params: {location_id: locationId},
            }).then(
                function (response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getAwcLocations');
                    return response.data.locations;
                },
                function () {
                    gtag.event('Location Service', 'Fetching data failed', 'getAwcLocations');
                }
            );
        },
        transformLocationTypeName: transformLocationTypeName,
        locationTypesToDisplay: function (locationTypes) {
            return _.map(locationTypes, function (locationType) {
                return transformLocationTypeName(locationType.name);
            }).join(', ');
        },
        locationTypeIsVisible: function (selectedLocations, level) {
            // whether a location type is visible (should be selectable) from locations service
            // hard code reports that disallow drilling past a certain level
            if (($location.path().indexOf('ls_launched') !== -1 || $location.path().indexOf('lady_supervisor') !== -1 || $location.path().indexOf('service_delivery_dashboard') !== -1) && level === sector_level) {
                return false;
            } else if (($location.path().indexOf('poshan_progress_dashboard') !== -1) && level === 1) {
                return false;
            }
            // otherwise
            return (
                level === 0 ||  // first level to select should be visible
                // or previous location should be set and not equal to "all".
                    (selectedLocations[level - 1] && selectedLocations[level - 1] !== ALL_OPTION.location_id && selectedLocations[level - 1].location_id !== ALL_OPTION.location_id)
            );
        },
        getLocationsForLevel: function (level, selectedLocations, locationsCache) {
            if (level === 0) {
                return locationsCache.root;
            } else {
                var selectedLocation = selectedLocations[level - 1];
                if (!selectedLocation || selectedLocation.location_id === ALL_OPTION.location_id) {
                    return [];
                }
                return locationsCache[selectedLocation.location_id];
            }
        },

        initHierarchy : function(locationHierarchy) {
            var hierarchy = _.map(locationHierarchy, function(locationType) {
                return {
                    name: locationType[0],
                    parents: locationType[1],
                };
            });

            var assignLevels = function(currentLocationType, level) {
                var children = _.filter(hierarchy, function(locationType) {
                    return _.contains(locationType.parents, currentLocationType);
                });
                children.forEach(function(child) {
                    child.level = level;
                    assignLevels(child.name, level + 1);
                });
            };
            assignLevels(null, 0);
            var maxLevel = _.max(hierarchy, function(locationType) {
                return locationType.level;
            }).level;
            var newHierarchy = _.toArray(_.groupBy(hierarchy, function(locationType) {
                return locationType.level;
            }));
            return {
                hierarchy: newHierarchy,
                levels: maxLevel,
            }
        },

        initLocations : function(vm, locationsCache) {
            var locationsService = this;
            if (vm.selectedLocationId) {
                vm.locationPromise = locationsService.getAncestors(vm.selectedLocationId).then(function(data) {
                    var locations = data.locations;

                    var selectedLocation = data.selected_location;

                    var locationsGroupedByParent = _.groupBy(locations, function(location) {
                        return location.parent_id || 'root';
                    });

                    for (var parentId in locationsGroupedByParent) {
                        if (locationsGroupedByParent.hasOwnProperty(parentId)) {
                            var sortedLocations = _.sortBy(locationsGroupedByParent[parentId], function (o) {
                                return o.name;
                            });
                            if (vm.preventShowingAllOption(sortedLocations)) {
                                locationsCache[parentId] = sortedLocations;
                            } else if (selectedLocation.user_have_access) {
                                locationsCache[parentId] = [ALL_OPTION].concat(sortedLocations);
                            } else {
                                locationsCache[parentId] = sortedLocations;
                            }
                        }
                    }

                    var levelOfSelectedLocation = _.findIndex(vm.hierarchy, function(locationTypes) {
                        return _.contains(_.pluck(locationTypes, 'name'), selectedLocation.location_type_name);
                    });
                    vm.selectedLocations[levelOfSelectedLocation] = vm.selectedLocationId;
                    locationsService.onSelectLocation(selectedLocation, levelOfSelectedLocation, locationsCache, vm);

                    levelOfSelectedLocation -= 1;

                    while(levelOfSelectedLocation >= 0) {
                        var childSelectedId = vm.selectedLocations[levelOfSelectedLocation + 1];
                        var childSelected = _.find(locations, function(location) {
                            return location.location_id === childSelectedId;
                        });
                        vm.selectedLocations[levelOfSelectedLocation] = childSelected.parent_id;
                        levelOfSelectedLocation -= 1;
                    }

                    var locationIndex = locationsService.selectedLocationIndex(vm.selectedLocations);
                    var levels = _.filter(vm.levels, function (value){return value.id > locationIndex;});
                    vm.groupByLevels = levels;
                    vm.selectedLevel = locationIndex + 1;
                });
            } else {
                vm.locationPromise = locationsService.getRootLocations().then(function(data) {
                    locationsCache.root = [NATIONAL_OPTION].concat(data.locations);
                });
                vm.groupByLevels = vm.levels;
            }
            return locationsCache;
        },

        onSelectLocation : function(item, level, locationsCache, vm) {
            this.resetLevelsBelow(level, vm);
            if (level < sector_level) {
                vm.locationPromise = this.getChildren(item.location_id).then(function (data) {
                    if (item.user_have_access) {
                        locationsCache[item.location_id] = [ALL_OPTION].concat(data.locations);
                        vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
                    } else {
                        locationsCache[item.location_id] = data.locations;
                        vm.selectedLocations[level + 1] = data.locations[0].location_id;
                        this.onSelectLocation(data.locations[0], level + 1, locationsCache, vm);
                    }
                });
            }
            var locationIndex = this.selectedLocationIndex(vm.selectedLocations);
            vm.selectedLocationId = vm.selectedLocations[locationIndex];
            vm.selectedLocation = item;
            var levels = _.filter(vm.levels, function (value){return value.id > locationIndex;});
            vm.selectedLevel = locationIndex + 1;
            vm.groupByLevels = levels;
        },

        getLocationPlaceholder : function(locationTypes, disallowNational) {
            return _.map(locationTypes, function(locationType) {
                if (locationType.name === 'state') {
                    if (disallowNational) {
                        return 'Select State';
                    } else {
                        return NATIONAL_OPTION.name;
                    }
                }
                return locationType.name;
            }).join(', ');
        },

        isLocationDisabled : function(level, vm) {
            if (vm.userLocationId === null) {
                return false;
            }
            var enabledLocationsForLevel = 0;
            window.angular.forEach(vm.getLocationsForLevel(level), function(location) {
                if (location.user_have_access || location.user_have_access_to_parent) {
                    enabledLocationsForLevel += 1;
                }
            });

            return enabledLocationsForLevel <= 1;
        },

        selectedLocationIndex : function(selectedLocations) {
            return _.findLastIndex(selectedLocations, function(locationId) {
                return locationId && locationId !== ALL_OPTION.location_id;
            });
        },

        getLocations : function(level, locationsCache, selectedLocations, disallowNational) {
            if (level === 0) {
                if (disallowNational && locationsCache.root) {
                    return locationsCache.root.slice(1);
                }
                return locationsCache.root;
            } else {
                var selectedLocation = selectedLocations[level - 1];
                if (!selectedLocation || selectedLocation === ALL_OPTION.location_id) {
                    return [];
                }
                return locationsCache[selectedLocation];
            }
        },
        
        resetLevelsBelow : function(level, vm) {
            // for the reports like THR report which does not allow download
            // below block level. So, if you switch from a report which does
            // allow download below block level to THR report and does not change
            // the location and directly click the export. The location_id which is sent
            // is not the block level but the lower level location selected in previous report
            if (vm.selectedLocationLevel > level && vm.selectedLocations[level]) {
                vm.selectedLocationId = vm.selectedLocations[level];
            }
            for (var i = level + 1; i <= vm.maxLevel; i++) {
                vm.hierarchy[i].selected = null;
                vm.selectedLocations[i] = null;
            }
        },
    };
}]);
