function LocationModalController($uibModalInstance, locationsService, selectedLocationId, hierarchy, selectedLocations, locationsCache, maxLevel, userLocationId) {
    var vm = this;

    var ALL_OPTION = {name: 'All', location_id: 'all'};

    vm.locationsCache = locationsCache;
    vm.userLocationId = userLocationId;
    vm.selectedLocationId = selectedLocationId;
    vm.hierarchy = hierarchy;
    vm.selectedLocations = selectedLocations;

    vm.getPlaceholder = function(locationTypes) {
        return _.map(locationTypes, function(locationType) {
            return locationType.name;
        }).join(', ');
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            return vm.locationsCache.root;
        } else {
            var selectedLocation = vm.selectedLocations[level - 1];
            if (!selectedLocation || selectedLocation === 'all') {
                return [];
            }
            return vm.locationsCache[selectedLocation];
        }
    };

    var selectedLocationIndex = function() {
        return _.findLastIndex(vm.selectedLocations, function(locationId) {
            return locationId && locationId !== ALL_OPTION.location_id;
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
        return selectedLocationIndex() !== -1 && selectedLocationIndex() >= level;
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);

        locationsService.getChildren($item.location_id).then(function(data) {
            vm.locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
        });
        vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
    };

    vm.apply = function() {
        vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
        $uibModalInstance.close(vm.selectedLocations);
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };

    vm.isVisible = function(level) {
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all');
    };
}


function LocationFilterController($scope, $location, $uibModal, locationHierarchy, locationsService, storageService) {
    var vm = this;
    $location.search(storageService.get());
    vm.animationsEnabled = true;
    vm.selectedLocationId = $location.search()['location'] || vm.selectedLocationId;
    vm.locationsCache = {};
    vm.selectedLocations = [];
    vm.hierarchy = [];
    vm.currentLevel = 0;
    vm.maxLevel = 0;

    var ALL_OPTION = {name: 'All', location_id: 'all'};

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

    var init = function() {
        if (vm.selectedLocationId && vm.selectedLocationId !== 'all') {
            locationsService.getAncestors(vm.selectedLocationId).then(function(data) {
                var locations = data.locations;

                var selectedLocation = data.selected_location;

                var locationsGrouppedByParent = _.groupBy(locations, function(location) {
                    return location.parent_id || 'root';
                });

                for (var parentId in locationsGrouppedByParent) {
                    if (locationsGrouppedByParent.hasOwnProperty(parentId)) {
                        vm.locationsCache[parentId] = [ALL_OPTION].concat(locationsGrouppedByParent[parentId]);
                    }
                }

                initHierarchy();

                var levelOfSelectedLocation = _.findIndex(vm.hierarchy, function(locationTypes) {
                    return _.contains(locationTypes.map(function(x) { return x.name; }), selectedLocation.location_type);
                });
                vm.selectedLocations[levelOfSelectedLocation] = vm.selectedLocationId;
                vm.onSelect(selectedLocation, levelOfSelectedLocation);

                levelOfSelectedLocation -= 1;

                while(levelOfSelectedLocation >= 0) {
                    var childSelectedId = vm.selectedLocations[levelOfSelectedLocation + 1];
                    var childSelected = _.find(locations, function(location) {
                        return location.location_id === childSelectedId;
                    });
                    vm.selectedLocations[levelOfSelectedLocation] = childSelected.parent_id;
                    levelOfSelectedLocation -= 1;
                }
            });
        } else {
            initHierarchy();
            locationsService.getRootLocations().then(function(data) {
                vm.locationsCache.root = [ ALL_OPTION ].concat(data.locations);
                vm.selectedLocations[0] = ALL_OPTION.location_id;
            });
        }
    };

    init();

    var resetLevelsBelow = function(level) {
        for (var i = level + 1; i <= vm.maxLevel; i++) {
            vm.hierarchy[i].selected = null;
            vm.selectedLocations[i] = null;
        }
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);

        locationsService.getChildren($item.location_id).then(function(data) {
            vm.locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
        });
        vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            return vm.locationsCache.root;
        } else {
            var selectedLocation = vm.selectedLocations[level - 1];
            if (!selectedLocation || selectedLocation === ALL_OPTION.location_id) {
                return [];
            }
            return vm.locationsCache[selectedLocation];
        }
    };

    var selectedLocationIndex = function() {
        return _.findLastIndex(vm.selectedLocations, function(locationId) {
            return locationId && locationId !== ALL_OPTION.location_id;
        });
    };

    vm.open = function () {
        var modalInstance = $uibModal.open({
            animation: vm.animationsEnabled,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'locationModalContent.html',
            controller: LocationModalController,
            controllerAs: '$ctrl',
            resolve: {
                location: function () {
                    return vm.location;
                },
                selectedLocationId: function () {
                    return vm.selectedLocationId;
                },
                hierarchy: function () {
                    return vm.hierarchy;
                },
                selectedLocations: function () {
                    return vm.selectedLocations;
                },
                locationsCache: function () {
                    return vm.locationsCache;
                },
                maxLevel: function () {
                    return vm.maxLevel;
                },
            },
        });

        modalInstance.result.then(function (selectedLocations) {
            vm.selectedLocations = selectedLocations;
            vm.currentLevel = selectedLocationIndex();
            vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
            vm.location = vm.selectedLocationId;

            var selectedLocationId = vm.selectedLocationId;

            if (selectedLocationIndex() >= 0) {
                var locations = vm.getLocationsForLevel(selectedLocationIndex());
                var loc = _.filter(locations, function (loc) {
                    return loc.location_id === vm.selectedLocationId;
                });
                $location.search('location_name', loc[0]['name']);
            } else if (selectedLocationIndex() === -1) {
                delete $location.search()['location_name'];
                selectedLocationId = ALL_OPTION.location_id;
            }
            $location.search('location', selectedLocationId);
            $location.search('selectedLocationLevel', selectedLocationIndex());
            storageService.set($location.search());
            $scope.$emit('filtersChange');
        });
    };

    $scope.$watch(function () {
        return $location.search();
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        var location = _.filter(vm.getLocationsForLevel(selectedLocationIndex() + 1), function(loc) {
            return loc.name === $location.search()['location_name'];
        });
        if (location.length > 0) {
            var loc_from_map = location[0];
            if (loc_from_map['name'] === newValue['location_name']) {
                vm.selectedLocationId = loc_from_map['location_id'];
                $location.search('selectedLocationLevel', selectedLocationIndex() + 1);
                $location.search('location', location[0]['location_id']);
            }
        }
    }, true);
}

LocationFilterController.$inject = ['$scope', '$location', '$uibModal', 'locationHierarchy', 'locationsService', 'storageService'];
LocationModalController.$inject = ['$uibModalInstance', 'locationsService', 'selectedLocationId', 'hierarchy', 'selectedLocations', 'locationsCache', 'maxLevel', 'userLocationId'];

window.angular.module('icdsApp').directive("locationFilter", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            location: '=',
            selectedLocationId: '=ngModel',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'location_filter'),
        controller: LocationFilterController,
        controllerAs: "$ctrl",
    };
});

