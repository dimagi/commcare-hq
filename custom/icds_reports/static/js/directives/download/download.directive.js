/* global moment */

function DownloadController($rootScope, $location, locationHierarchy, locationsService, userLocationId, haveAccessToFeatures,
                            issnipService) {
    var vm = this;

    vm.months = [];
    vm.monthsCopy = [];
    vm.years = [];
    vm.task_id = $location.search()['task_id'] || '';
    $rootScope.issnip_report_link = '';

    var getISSNIPStatus = function () {
        issnipService.getStatus(vm.task_id).then(function (resp) {
            if (resp.task_ready) {
                clearInterval(vm.statusCheck);
                $rootScope.issnip_task_id = '';
                $rootScope.issnip_report_link = resp.task_result.link;
                vm.queuedISSNIPTask = false;
            }
        });
    };

    if (vm.task_id) {
        $rootScope.issnip_task_id = vm.task_id;
        $location.search('task_id', null);
        vm.statusCheck = setInterval(getISSNIPStatus, 5 * 1000);
    }

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

    vm.selectedMonth = new Date().getMonth() + 1;
    vm.selectedYear = new Date().getFullYear();

    window.angular.forEach(moment.months(), function(key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });

    if (vm.selectedYear === new Date().getFullYear()) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id <= new Date().getMonth() + 1;
        });
    } else {
        vm.months = vm.monthsCopy;
    }

    for (var year=2014; year <= new Date().getFullYear(); year++ ) {
        vm.years.push({
            name: year,
            id: year,
        });
    }
    vm.queuedISSNIPTask = false;
    vm.selectedIndicator = 1;
    vm.selectedFormat = 'xls';
    vm.selectedPDFFormat = 'many';
    vm.selectedLocationId = userLocationId;
    vm.selectedLevel = 1;
    vm.now = new Date().getMonth() + 1;
    vm.showWarning = function () {
        return (
            vm.now === vm.selectedMonth &&
            new Date().getFullYear() === vm.selectedYear
        );
    };
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

    vm.pdfFormats = [
        {id: 'many', name: 'One PDF per AWC'},
        {id: 'one', name: 'One Combined PDF for all AWCs'},
    ];
    vm.downloaded = false;

    vm.awcLocations = [];
    vm.selectedAWCs = [];

    vm.indicators = [
        {id: 1, name: 'Child'},
        {id: 2, name: 'Pregnant Women'},
        {id: 3, name: 'Demographics'},
        {id: 4, name: 'System Usage'},
        {id: 5, name: 'AWC Infrastructure'},
        {id: 6, name: 'Child Beneficiary List'},

    ];

    if (haveAccessToFeatures) {
        vm.indicators.push({id: 7, name: 'ICDS-CAS Monthly Register'});
    }

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

    vm.onSelectForISSNIP = function ($item, level) {
        var selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
        locationsService.getAwcLocations(selectedLocationId).then(function (data) {
            vm.awcLocations = [ALL_OPTION].concat(data);
        });
        vm.selectedAWCs = [];
        vm.onSelect($item, level);
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

    vm.onSelectAWCs = function($item) {
        if ($item.location_id === 'all') {
            vm.selectedAWCs = [$item.location_id];
        } else if (vm.selectedAWCs.indexOf('all') !== -1) {
            vm.selectedAWCs = [$item.location_id];
        }
    };

    vm.onSelectYear = function (item) {
        if (item.id === new Date().getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function(month) {
                return month.id <= new Date().getMonth() + 1;
            });
            vm.selectedMonth = vm.selectedMonth <= new Date().getMonth() + 1 ? vm.selectedMonth : new Date().getMonth() + 1;
        } else {
            vm.months = vm.monthsCopy;
        }
    };

    vm.getAwcs = function () {
        locationsService.getAncestors();
    };

    vm.getFormats = function() {
        if (vm.isChildBeneficiaryListSelected()) {
            return [vm.formats[0]];
        } else {
            return vm.formats;
        }
    };

    vm.onIndicatorSelect = function() {
        if (vm.isChildBeneficiaryListSelected()) {
            init();
            vm.selectedFormat = vm.formats[0].id;
        } else {
            vm.selectedFormat = 'xls';
        }
    };

    vm.submitISSNIPForm = function(csrf_token) {
        $rootScope.issnip_report_link = '';
        var awcs = vm.selectedPDFFormat === 'one' ? ['all'] : vm.selectedAWCs;
        issnipService.createTask({
            'csrfmiddlewaretoken': csrf_token,
            'location': vm.selectedLocationId,
            'aggregation_level': vm.selectedLevel,
            'month': vm.selectedMonth,
            'year': vm.selectedYear,
            'indicator': vm.selectedIndicator,
            'format': vm.selectedFormat,
            'pdfformat': vm.selectedPDFFormat,
            'selected_awcs': awcs.join(','),
        }).then(function(data) {
            vm.task_id = data.task_id;
            if (vm.task_id) {
                $rootScope.issnip_task_id = vm.task_id;
                $location.search('task_id', null);
                vm.statusCheck = setInterval(getISSNIPStatus, 5 * 1000);
            }
        });
        vm.queuedISSNIPTask = true;
        vm.downloaded = false;
    };

    vm.resetForm = function() {
        vm.hierarchy = [];
        vm.selectedLocations = [];
        vm.selectedLocationId = userLocationId;
        vm.selectedLevel = 1;
        vm.selectedMonth = new Date().getMonth() + 1;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedIndicator = 1;
        vm.selectedFormat = 'xls';
        vm.selectedPDFFormat = 'many';
        initHierarchy();
    };

    vm.hasErrors = function() {
        return vm.isChildBeneficiaryListSelected() && (vm.selectedFilterOptions().length === 0 || !vm.isDistrictOrBelowSelected());
    };

    vm.hasErrorsISSNIPExport = function() {
        if (vm.selectedPDFFormat === 'one') {
            return vm.isISSNIPMonthlyRegisterSelected() && !vm.isDistrictOrBelowSelected();
        }
        return vm.isISSNIPMonthlyRegisterSelected() && (!vm.isDistrictOrBelowSelected() || !vm.isAWCsSelected());
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

    vm.isISSNIPMonthlyRegisterSelected = function () {
        return vm.selectedIndicator === 7;
    };

    vm.isDistrictOrBelowSelected = function() {
        return vm.selectedLocations[1] && vm.selectedLocations[1] !== ALL_OPTION.location_id;
    };

    vm.isAWCsSelected = function() {
        return vm.selectedAWCs.length > 0;
    };

    vm.showProgressBar = function () {
        return $rootScope.issnip_task_id;
    };

    vm.readyToDownload = function () {
        return $rootScope.issnip_report_link;
    };

    vm.goToLink = function () {
        window.open($rootScope.issnip_report_link);
        vm.downloaded = true;
        $rootScope.issnip_report_link = '';
    };

}

DownloadController.$inject = ['$rootScope', '$location', 'locationHierarchy', 'locationsService', 'userLocationId',
    'haveAccessToFeatures', 'issnipService'];

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
