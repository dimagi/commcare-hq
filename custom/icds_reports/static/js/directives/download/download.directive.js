/* global moment */

function DownloadController($location, locationHierarchy, locationsService, userLocationId) {
    var vm = this;

    vm.months = [];
    vm.years = [];

    vm.filterOptions = [
        {label: 'Data not Entered for weight (Unweighed)', id: 'unweighed'},
        {label: 'Data not Entered for height (Unmeasured)', id: 'umeasured'},
        {label: 'Severely Underweight', id: 'severely_underweight'},
        {label: 'Moderately Underweight', id: 'moderately_underweight'},
        {label: 'Normal (weight-for-age)', id: 'normal_wfa'},
        {label: 'Severely Stunted', id: 'severely_stunted'},
        {label: 'Moderately Stunted', id: 'moderately_stunted'},
        {label: 'Normal (height-for-age)', id: 'normal_hfa'},
        {label: 'Severely Wasted', id: 'severely_wasted'},
        {label: 'Moderately Wasted', id: 'moderately_wasted'},
        {label: 'Normal (weight-for-height)', id: 'normal_wfh'},
    ];

    vm.userLocationId = userLocationId;

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
    vm.selectedLocationId = userLocationId;
    vm.selectedLevel = 1;
    vm.now = new Date().getMonth() + 1;
    vm.levels = [
        {id: 1, name: 'State'},
        {id: 2, name: 'District'},
        {id: 3, name: 'Block'},
        {id: 4, name: 'Supervisor'},
        {id: 5, name: 'AWC'},
    ];

    vm.groupByLevels = [];

    vm.formats = [
        {id: 'csv', name: 'CSV'},
        {id: 'xls', name: 'Excel'},
    ];

    vm.indicators = [
        {id: 1, name: 'Child'},
        {id: 2, name: 'Pregnant Women'},
        {id: 3, name: 'Demographics'},
        {id: 4, name: 'System Usage'},
        {id: 5, name: 'AWC Infrastructure'},
        {id: 6, name: 'Child Beneficiary List'},
    ];

    var ALL_OPTION = {name: 'All', location_id: 'all'};
    var NATIONAL_OPTION = {name: 'National', location_id: 'all'};

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
                    return _.contains(locationTypes.map(function(x) { return x.name; }), selectedLocation.location_type_name);
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

                var levels = [];
                window.angular.forEach(vm.levels, function (value) {
                    if (value.id > selectedLocationIndex()) {
                        levels.push(value);
                    }
                });
                vm.groupByLevels = levels;
                vm.selectedLevel = selectedLocationIndex() + 1;
            });
        } else {
            initHierarchy();
            locationsService.getRootLocations().then(function(data) {
                locationsCache.root = [NATIONAL_OPTION].concat(data.locations);
            });
            vm.groupByLevels = vm.levels;
        }
    };

    init();

    vm.getPlaceholder = function(locationTypes) {
        return _.map(locationTypes, function(locationType) {
            if (locationType.name === 'state') {
                if (vm.isChildBeneficiaryListSelected()) {
                    return 'Select State';
                } else {
                    return NATIONAL_OPTION.name;
                }
            }
            return locationType.name;
        }).join(', ');
    };

    vm.showErrorMessage = function () {
        return vm.selectedIndicator === 6 && selectedLocationIndex() !== 4;
    };

    vm.getLocationsForLevel = function(level) {
        if (level === 0) {
            if (vm.isChildBeneficiaryListSelected()) {
                return locationsCache.root.slice(1);
            }
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

    vm.disabled = function(level) {
        if (vm.userLocationId === null) {
            return false;
        }
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key === userLocationId) {
                i = value;
            }
        });
        return selectedLocationIndex() !== -1 && i >= level;
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);

        locationsService.getChildren($item.location_id).then(function(data) {
            locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
        });
        var levels = [];
        window.angular.forEach(vm.levels, function (value) {
            if (value.id > selectedLocationIndex()) {
                levels.push(value);
            }
        });
        vm.groupByLevels = levels;
        vm.selectedLevel = selectedLocationIndex() + 1;

        vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
        vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
    };

    vm.getFormats = function() {
        if (vm.isChildBeneficiaryListSelected()) {
            return [vm.formats[0]];
        } else {
            return vm.formats;
        }
    };

    vm.onIndicatorSelect = function() {
        if (vm.isChildBeneficiaryListSelected() && !vm.isDistrictOrBelowSelected()) {
            init();
            vm.selectedFormat = vm.formats[0].id;
        } else {
            vm.selectedFormat = 'xls';
        }
    };

    vm.hasErrors = function() {
        return vm.isChildBeneficiaryListSelected() && (vm.selectedFilterOptions().length === 0 || !vm.isDistrictOrBelowSelected());
    };

    vm.isVisible = function(level) {
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all');
    };

    vm.selectedFilterOptions = function() {
        return vm.filterOptions.filter(function(el) {
            return el.selected;
        });
    };

    vm.isChildBeneficiaryListSelected = function() {
        return vm.selectedIndicator === 6;
    };

    vm.isDistrictOrBelowSelected = function() {
        return vm.selectedLocations[1] && vm.selectedLocations[1] !== ALL_OPTION.location_id;
    };
}

DownloadController.$inject = ['$location', 'locationHierarchy', 'locationsService', 'userLocationId'];

window.angular.module('icdsApp').directive("download", function() {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
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
