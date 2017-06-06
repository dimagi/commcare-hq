function DownloadController($location, locationHierarchy, locationsService) {
    var vm = this;

    vm.months = [];
    vm.years = [];

    window.angular.forEach(moment.months(), function(key, value) {
        vm.months.push({
            name: key,
            id: value + 1,
        });
    });

    for (var year=2014; year <= new Date().getFullYear(); year++ ) {
        vm.years.push({
            name: year,
            id: year,
        });
    }

    vm.selectedMonth = new Date().getMonth() + 1;
    vm.selectedYear = new Date().getFullYear();
    vm.selectedIndicator = 1;
    vm.selectedFormat = 'xls';
    vm.selectedGender = '';
    vm.selectedAge = '';
    vm.selectedLocationId = '';

    vm.genders = [
        {id: '', name: 'All'},
        {id: 'M', name: 'Male'},
        {id: 'F', name: 'Female'},
    ];

    vm.formats = [
        {id: 'csv', name: 'CSV'},
        {id: 'xls', name: 'Excel'},
    ];

    vm.ages = [
        {id: '', name: 'All'},
        {id: '0', name: '0 months'},
        {id: '6', name: '6 months'},
        {id: '12', name: '12 months'},
        {id: '24', name: '24 months'},
        {id: '36', name: '36 months'},
        {id: '48', name: '48 months'},
        {id: '60', name: '60 months'},
        {id: '72', name: '72 months'},
    ];

    vm.indicators = [
        {id: 1, name: 'MCH'},
        {id: 2, name: 'System Usage'},
        {id: 3, name: 'Demographics'},
        {id: 4, name: 'AWC Infrastructure'},
    ];

    var ALL_OPTION = {name: 'All', location_id: 'all'};

    var locationsCache = {};

    vm.hierarchy = [];
    vm.selectedLocations = [];

    var maxLevel = 0;

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
        maxLevel = _.max(hierarchy, function(locationType) {
            return locationType.level;
        }).level;
        vm.hierarchy = _.toArray(_.groupBy(hierarchy, function(locationType) {
            return locationType.level;
        }));
        vm.selectedLocations = new Array(maxLevel);
    };

    var init = function() {
        if (vm.selectedLocationId) {
            locationsService.getAncestors(vm.selectedLocationId).then(function(data) {
                var locations = data.locations;

                var selectedLocation = data.selected_location;

                var locationsGrouppedByParent = _.groupBy(locations, function(location) {
                    return location.parent_id || 'root';
                });

                for (var parentId in locationsGrouppedByParent) {
                    if (locationsGrouppedByParent.hasOwnProperty(parentId)) {
                        locationsCache[parentId] = [ALL_OPTION].concat(locationsGrouppedByParent[parentId]);
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
                locationsCache.root = data.locations;
            });
        }
    };

    init();

    vm.getPlaceholder = function(locationTypes) {
        return _.map(locationTypes, function(locationType) {
            return locationType.name;
        }).join(', ');
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            return locationsCache.root;
        } else {
            var selectedLocation = vm.selectedLocations[level - 1];
            if (!selectedLocation || selectedLocation === ALL_OPTION.location_id) {
                return [];
            }
            return locationsCache[selectedLocation];
        }
    };

    var resetLevelsBelow = function(level) {
        for (var i = level + 1; i <= maxLevel; i++) {
            vm.hierarchy[i].selected = null;
            vm.selectedLocations[i] = null;
        }
    };

    var selectedLocationIndex = function() {
        return _.findLastIndex(vm.selectedLocations, function(locationId) {
            return locationId && locationId !== ALL_OPTION.location_id;
        });
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);

        locationsService.getChildren($item.location_id).then(function(data) {
            locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
        });

        vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
        vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
    };

    vm.isVisible = function(level) {
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all');
    };
}

DownloadController.$inject = ['$location', 'locationHierarchy', 'locationsService'];

window.angular.module('icdsApp').directive("download", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'download.directive'),
        controller: DownloadController,
        controllerAs: "$ctrl",
    };
});
