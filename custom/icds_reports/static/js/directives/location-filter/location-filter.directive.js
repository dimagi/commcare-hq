/* global _, LocationModalController, LocationFilterController */
var transformLocationTypeName = function(locationTypeName) {
    if (locationTypeName === 'awc') {
        return locationTypeName.toUpperCase();
    } else if (locationTypeName === 'supervisor') {
        return 'Sector';
    } else {
        return locationTypeName.charAt(0).toUpperCase() + locationTypeName.slice(1);
    }
};

function LocationModalController($uibModalInstance, $location, locationsService, selectedLocationId, hierarchy, selectedLocations, locationsCache, maxLevel, userLocationId, showMessage, showSectorMessage) {
    var vm = this;

    var ALL_OPTION = {
        name: 'All',
        location_id: 'all',
        user_have_access: 0,
        user_have_access_to_parent: 1,
    };

    vm.locationsCache = locationsCache;
    vm.userLocationId = userLocationId;
    vm.selectedLocationId = selectedLocationId || ALL_OPTION;
    vm.hierarchy = hierarchy;
    vm.selectedLocations = selectedLocations;
    vm.showMessage = showMessage;
    vm.showSectorMessage = showSectorMessage;

    vm.errors = function () {
        return vm.showMessage || vm.showSectorMessage;
    };

    vm.locationIsNull = function (location) {
        return location === null || location === void(0) || location.location_id === 'all';
    };

    vm.getPlaceholder = function(locationTypes) {
        return _.map(locationTypes, function(locationType) {
            return transformLocationTypeName(locationType.name);
        }).join(', ');
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            return vm.locationsCache.root;
        } else {
            var selectedLocation = vm.selectedLocations[level - 1];
            if (!selectedLocation || selectedLocation.location_id === 'all') {
                return [];
            }
            return vm.locationsCache[selectedLocation.location_id];
        }
    };

    var selectedLocationIndex = function() {
        return _.findLastIndex(vm.selectedLocations, function(location) {
            return location && location !== ALL_OPTION.location_id;
        });
    };

    var resetLevelsBelow = function(level) {
        for (var i = level + 1; i <= maxLevel; i++) {
            vm.hierarchy[i].selected = null;
            vm.selectedLocations[i] = null;
        }
    };

    vm.disabled = function(level) {
        if (vm.userLocationId === null) {
            return false;
        }
        var notDisabledLocationsForLevel = 0;
        window.angular.forEach(vm.getLocationsForLevel(level), function(location) {
            if (location.user_have_access || location.user_have_access_to_parent) {
                notDisabledLocationsForLevel += 1;
            }
        });
        return notDisabledLocationsForLevel <= 1;
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);
        if ($location.path().indexOf('awc_reports') !== -1) {
            vm.showMessage = vm.locationIsNull(vm.selectedLocations[4]);
        }
        if ($location.path().indexOf('lady_supervisor') !== -1) {
            vm.showSectorMessage = vm.locationIsNull(vm.selectedLocations[3]) || selectedLocationIndex() !== 3;
        }
        if (level < 4 && $item) {
            vm.myPromise = locationsService.getChildren($item.location_id).then(function (data) {
                if ($item.user_have_access) {
                    vm.locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
                    vm.selectedLocations[level + 1] = ALL_OPTION;
                } else {
                    vm.locationsCache[$item.location_id] = data.locations;
                    vm.selectedLocations[level + 1] = data.locations[0];
                    vm.onSelect(data.locations[0], level + 1);
                }
            });
        }
    };

    vm.apply = function() {
        vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
        hqImport('analytix/js/google').track.event(
            'Location Filter',
            'Location Changed',
            vm.selectedLocationId.location_id
        );
        $uibModalInstance.close(vm.selectedLocations);
    };

    vm.reset = function() {
        if (vm.userLocationId !== null) {
            var i = -1;
            window.angular.forEach(vm.selectedLocations, function (key, value) {
                if (key !== null && key.location_id === vm.userLocationId) {
                    i = value;
                }
            });
            vm.selectedLocations = vm.selectedLocations.slice(0, i + 1);
            vm.selectedLocations.push(ALL_OPTION);
            vm.selectedLocationId = vm.userLocationId;
        } else {
            vm.selectedLocations = [ALL_OPTION];
            vm.selectedLocationId = null;
        }
    };

    vm.isAwcReport = function () {
        return $location.path().indexOf('awc_reports') !== -1;
    };

    vm.isLSReport = function () {
        return $location.path().indexOf('lady_supervisor') !== -1;
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };

    vm.isVisible = function(level) {
        if (($location.path().indexOf('lady_supervisor') !== -1 || $location.path().indexOf('service_delivery_dashboard') !== -1) && level === 4) {
            return false;
        }
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all' && vm.selectedLocations[level - 1].location_id !== 'all');
    };
}


function LocationFilterController($rootScope, $scope, $location, $uibModal, $uibModalStack, locationHierarchy, locationsService, storageService, userLocationId, haveAccessToAllLocations, allUserLocationId) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }

    vm.userLocationId = userLocationId;
    vm.allUserLocationId = allUserLocationId;
    vm.animationsEnabled = true;

    function locationIdIsNullOrEmpty() {
        var emptyValues = ['undefined', 'null'];
        if (!haveAccessToAllLocations) {
            emptyValues.push('');
        }
        return emptyValues.indexOf($location.search()['location_id']) === -1;
    }

    vm.selectedLocationId = locationIdIsNullOrEmpty() ? $location.search()['location_id'] : vm.userLocationId;

    vm.locationsCache = {};
    vm.selectedLocations = [];
    vm.hierarchy = [];
    vm.currentLevel = 0;
    vm.maxLevel = 0;
    vm.location_id = $location.search()['location_id'] !== 'undefined' &&
        $location.search()['location_id'] !== 'null' ? $location.search()['location_id'] : vm.selectedLocationId;

    var ALL_OPTION = {
        name: 'All',
        location_id: 'all',
        "user_have_access": 0,
        "user_have_access_to_parent": 1,
    };

    var initHierarchy = function() {
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
        vm.maxLevel = _.max(hierarchy, function(locationType) {
            return locationType.level;
        }).level;
        vm.hierarchy = _.toArray(_.groupBy(hierarchy, function(locationType) {
            return locationType.level;
        }));
        vm.selectedLocations = new Array(vm.maxLevel);
    };

    vm.isAwcReport = function () {
        return $location.path().indexOf('awc_reports') !== -1;
    };

    vm.isLSReport = function () {
        return $location.path().indexOf('lady_supervisor') !== -1;
    };

    vm.open = function () {
        $uibModalStack.dismissAll();
        var modalInstance = $uibModal.open({
            animation: vm.animationsEnabled,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'locationModalContent.html',
            controller: LocationModalController,
            controllerAs: '$ctrl',
            backdrop: vm.isAwcReport() || vm.isLSReport() ? 'static' : true,
            resolve: {
                location_id: function () {
                    return vm.location_id;
                },
                selectedLocationId: function () {
                    return vm.selectedLocationId;
                },
                hierarchy: function () {
                    return vm.hierarchy;
                },
                selectedLocations: function () {
                    return window.angular.copy(vm.selectedLocations);
                },
                locationsCache: function () {
                    return vm.locationsCache;
                },
                maxLevel: function () {
                    return vm.maxLevel;
                },
                showMessage: function () {
                    return vm.isOpenModal;
                },
                showSectorMessage: function () {
                    return $location.path().indexOf('lady_supervisor') !== -1 && selectedLocationIndex() !== 3;
                },
            },
        });

        modalInstance.result.then(function (selectedLocations) {
            vm.selectedLocations = selectedLocations;
            vm.currentLevel = selectedLocationIndex();
            vm.selectedLocation = vm.selectedLocations[selectedLocationIndex()];

            if (selectedLocationIndex() >= 0) {
                vm.selectedLocationId = vm.selectedLocation.location_id;
                vm.location_id = vm.selectedLocationId;
                var locations = vm.getLocationsForLevel(selectedLocationIndex());
                var loc = _.filter(locations, function (loc) {
                    return loc.location_id === vm.selectedLocationId;
                });
                $location.search('location_name', loc[0]['name']);
                $location.search('location_id', vm.selectedLocationId);
                $location.search('selectedLocationLevel', selectedLocationIndex());
            } else if (selectedLocationIndex() === -1) {
                $location.search('location_name', '');
                $location.search('location_id', '');
                $location.search('selectedLocationLevel', '');
                vm.location_id = 'all';
            }
            storageService.setKey('search', $location.search());
            if (selectedLocationIndex() === 4 && $location.path().indexOf('awc_reports') === -1) {
                $location.path('awc_reports');
            }
            $scope.$emit('filtersChange');
        });
    };

    vm.userHaveAccessToAllLocations = function(locations) {
        var haveAccessToAllLocationsForLevel = true;
        window.angular.forEach(locations, function (location) {
            if (!location.user_have_access) {
                haveAccessToAllLocationsForLevel = false;
            }
        });
        return haveAccessToAllLocationsForLevel;
    };

    vm.userLocationIdIsNull = function() {
        return ["null", "undefined"].indexOf(vm.userLocationId) !== -1;
    };

    vm.isUserLocationIn = function(locations) {
        var userLocationInSorted = _.filter(locations, function (location) {
            return vm.allUserLocationId.indexOf(location.location_id) !== -1;
        });
        return userLocationInSorted.length > 0;
    };

    vm.showAllOption = function(locations) {
        return ((!vm.userLocationIdIsNull() && !vm.userHaveAccessToAllLocations(locations)) || vm.isUserLocationIn(locations)) && !haveAccessToAllLocations;
    };

    var init = function() {
        if (vm.selectedLocationId && vm.selectedLocationId !== 'all' && vm.selectedLocationId !== 'null') {
            vm.myPromise = locationsService.getAncestors(vm.selectedLocationId).then(function(data) {
                var locations = data.locations;

                var selectedLocation = data.selected_location;

                var locationsGrouppedByParent = _.groupBy(locations, function(location) {
                    return location.parent_id || 'root';
                });

                for (var parentId in locationsGrouppedByParent) {
                    if (locationsGrouppedByParent.hasOwnProperty(parentId)) {
                        var sortedLocations = _.sortBy(locationsGrouppedByParent[parentId], function(o) {
                            return o.name;
                        });

                        if (vm.showAllOption(sortedLocations)) {
                            vm.locationsCache[parentId] = sortedLocations;
                        } else if (selectedLocation.user_have_access) {
                            vm.locationsCache[parentId] = [ALL_OPTION].concat(sortedLocations);
                        } else {
                            vm.locationsCache[parentId] = sortedLocations;
                        }
                    }
                }

                initHierarchy();

                var levelOfSelectedLocation = _.findIndex(vm.hierarchy, function(locationTypes) {
                    return _.contains(locationTypes.map(function(x) { return x.name; }), selectedLocation.location_type_name);
                });
                vm.selectedLocations[levelOfSelectedLocation] = selectedLocation;
                vm.onSelect(selectedLocation, levelOfSelectedLocation);
                storageService.setKey('selectedLocation', selectedLocation);

                levelOfSelectedLocation -= 1;

                while(levelOfSelectedLocation >= 0) {
                    var childSelectedId = vm.selectedLocations[levelOfSelectedLocation + 1];
                    var childSelected = _.find(locations, function(location) {
                        return location.location_id === childSelectedId.parent_id;
                    });
                    vm.selectedLocations[levelOfSelectedLocation] = childSelected;
                    levelOfSelectedLocation -= 1;
                }


                if (($location.path().indexOf('awc_reports') !== -1 && selectedLocationIndex() < 4) ||
                    ($location.path().indexOf('lady_supervisor') !== -1 && selectedLocationIndex() !== 3)) {
                    vm.open();
                }
                if ($location.path().indexOf('awc_reports') === -1 && selectedLocationIndex() === 4) {
                    vm.onSelect(vm.selectedLocations[3], 3);
                    vm.selectedLocationId = vm.selectedLocations[3].location_id;
                    vm.location_id = vm.selectedLocationId;
                    locations = vm.getLocationsForLevel(selectedLocationIndex());
                    var loc = _.filter(locations, function (loc) {
                        return loc.location_id === vm.selectedLocationId;
                    });
                    $location.search('location_name', loc[0]['name']);
                    $location.search('location_id', vm.selectedLocationId);
                    $location.search('selectedLocationLevel', selectedLocationIndex());
                    storageService.setKey('search', $location.search());
                    $scope.$emit('filtersChange');
                }
            });
        } else {
            initHierarchy();
            vm.myPromise = locationsService.getRootLocations().then(function(data) {
                vm.locationsCache.root = [ ALL_OPTION ].concat(data.locations);
                vm.selectedLocations[0] = ALL_OPTION;

                if (($location.path().indexOf('awc_reports') !== -1 && selectedLocationIndex() < 4) ||
                    ($location.path().indexOf('lady_supervisor') !== -1 && selectedLocationIndex() !== 3)) {
                    vm.open();
                }
                storageService.setKey('selectedLocation', {name: 'National'});
            });
        }

    };

    vm.getPlaceholder = function() {
        var selectedLocation = vm.selectedLocations[selectedLocationIndex()];

        if (!selectedLocation) {
            return 'Location';
        } else {
            var locationTypeName = selectedLocation.location_type_name;
            return transformLocationTypeName(locationTypeName);
        }
    };

    var resetLevelsBelow = function(level) {
        for (var i = level + 1; i <= vm.maxLevel; i++) {
            vm.hierarchy[i].selected = null;
            vm.selectedLocations[i] = null;
        }
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);
        if (level < 4) {
            vm.myPromise = locationsService.getChildren($item.location_id).then(function (data) {
                if ($item.user_have_access) {
                    vm.locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
                } else {
                    vm.locationsCache[$item.location_id] = data.locations;
                }
            });
            vm.selectedLocations[level + 1] = ALL_OPTION;
        }
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            return vm.locationsCache.root;
        } else {
            var selectedLocation = vm.selectedLocations[level - 1];
            if (!selectedLocation || selectedLocation.location_id === ALL_OPTION.location_id) {
                return [];
            }
            return _.sortBy(
                vm.locationsCache[selectedLocation.location_id], function(o) {
                    return o.name;
                }
            );
        }
    };

    var selectedLocationIndex = function() {
        return _.findLastIndex(vm.selectedLocations, function(location) {
            return location && location !== ALL_OPTION.location_id && location.location_id !== ALL_OPTION.location_id;
        });
    };

    $scope.$watch(function () {
        return $location.search();
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        var location = _.filter(vm.getLocationsForLevel(selectedLocationIndex() + 1), function(loc) {
            return loc.location_id === $location.search().location_id;
        });
        if (location.length > 0) {
            var loc_from_map = location[0];
            if (loc_from_map.location_id === newValue.location_id) {
                vm.selectedLocationId = loc_from_map['location_id'];
                $location.search('selectedLocationLevel', selectedLocationIndex() + 1);
                $location.search('location_id', location[0].location_id);
            }
        }
    }, true);

    init();
}

LocationFilterController.$inject = ['$rootScope', '$scope', '$location', '$uibModal', '$uibModalStack', 'locationHierarchy', 'locationsService', 'storageService', 'userLocationId', 'haveAccessToAllLocations', 'allUserLocationId'];
LocationModalController.$inject = ['$uibModalInstance', '$location', 'locationsService', 'selectedLocationId', 'hierarchy', 'selectedLocations', 'locationsCache', 'maxLevel', 'userLocationId', 'showMessage', 'showSectorMessage'];

window.angular.module('icdsApp').directive("locationFilter", function() {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict:'E',
        scope: {
            selectedLocationId: '=',
            selectedLocations: '=',
            isOpenModal: '=?',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'location_filter'),
        controller: LocationFilterController,
        controllerAs: "$ctrl",
    };
});

