/* global moment */

function DownloadController($rootScope, $location, locationHierarchy, locationsService, userLocationId, haveAccessToFeatures,
    downloadService) {
    var vm = this;

    vm.months = [];
    vm.monthsCopy = [];
    vm.years = [];
    vm.yearsCopy = [];
    vm.task_id = $location.search()['task_id'] || '';
    vm.haveAccessToFeatures = haveAccessToFeatures;
    vm.previousTaskFailed = null;
    $rootScope.report_link = '';

    var getTaskStatus = function () {
        downloadService.getStatus(vm.task_id).then(function (resp) {
            if (resp.task_ready) {
                clearInterval(vm.statusCheck);
                $rootScope.task_id = '';
                vm.previousTaskFailed = !resp.task_successful;
                $rootScope.report_link = resp.task_successful ? resp.task_result.link : '';
                vm.queuedTask = false;
            }
        });
    };

    if (vm.task_id) {
        $rootScope.task_id = vm.task_id;
        $location.search('task_id', null);
        vm.statusCheck = setInterval(getTaskStatus, 5 * 1000);
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
    } else if (vm.selectedYear === 2017) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id >= 3;
        });
    } else {
        vm.months = vm.monthsCopy;
    }

    for (var year=2017; year <= new Date().getFullYear(); year++ ) {
        vm.yearsCopy.push({
            name: year,
            id: year,
        });
    }
    vm.years = vm.yearsCopy;
    vm.queuedTask = false;
    vm.selectedIndicator = 1;
    vm.selectedFormat = 'xlsx';
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
        {id: 'xlsx', name: 'Excel'},
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
        {id: 7, name: 'ICDS-CAS Monthly Register'},
        {id: 8, name: 'AWW Performance Report'},
        {id: 9, name: 'LS Performance Report'},
    ];
    if (vm.haveAccessToFeatures) {
        vm.indicators.push({id: 10, name: 'Take Home Ration (THR)'});
    }

    var ALL_OPTION = {
        name: 'All',
        location_id: 'all',
        "user_have_access": 0,
        "user_have_access_to_parent": 1,
    };
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
            vm.myPromise = locationsService.getAncestors(vm.selectedLocationId).then(function(data) {
                var locations = data.locations;

                var selectedLocation = data.selected_location;

                var locationsGrouppedByParent = _.groupBy(locations, function(location) {
                    return location.parent_id || 'root';
                });

                for (var parentId in locationsGrouppedByParent) {
                    if (locationsGrouppedByParent.hasOwnProperty(parentId)) {
                        var sorted_locations = _.sortBy(locationsGrouppedByParent[parentId], function(o) {
                            return o.name;
                        });
                        if (selectedLocation.user_have_access) {
                            locationsCache[parentId] = [ALL_OPTION].concat(sorted_locations);
                        } else {
                            locationsCache[parentId] = sorted_locations;
                        }
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
            vm.myPromise = locationsService.getRootLocations().then(function(data) {
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
        var notDisabledLocationsForLevel = 0;
        window.angular.forEach(vm.getLocationsForLevel(level), function(location) {
            if (location.user_have_access || location.user_have_access_to_parent) {
                notDisabledLocationsForLevel += 1;
            }
        });

        return notDisabledLocationsForLevel <= 1;
    };

    vm.onSelectForISSNIP = function ($item, level) {
        var selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
        vm.myPromise = locationsService.getAwcLocations(selectedLocationId).then(function (data) {
            if ($item.user_have_access) {
                vm.awcLocations = [ALL_OPTION].concat(data);
            } else {
                vm.awcLocations = data;
            }
        });
        vm.selectedAWCs = [];
        vm.onSelect($item, level);
    };

    vm.onSelect = function($item, level) {
        resetLevelsBelow(level);
        if (level < 4) {
            vm.myPromise = locationsService.getChildren($item.location_id).then(function (data) {
                if ($item.user_have_access) {
                    locationsCache[$item.location_id] = [ALL_OPTION].concat(data.locations);
                    vm.selectedLocations[level + 1] = ALL_OPTION.location_id;
                } else {
                    locationsCache[$item.location_id] = data.locations;
                    vm.selectedLocations[level + 1] = data.locations[0].location_id;
                    if (level === 2 && vm.isISSNIPMonthlyRegisterSelected()) {
                        vm.onSelectForISSNIP(data.locations[0], level + 1);
                    } else {
                        vm.onSelect(data.locations[0], level + 1);
                    }
                }
            });
        }
        vm.selectedLocationId = vm.selectedLocations[selectedLocationIndex()];
        var levels = [];
        vm.selectedLevel = selectedLocationIndex() + 1;
        window.angular.forEach(vm.levels, function (value) {
            if (value.id > selectedLocationIndex()) {
                levels.push(value);
            }
        });
        vm.groupByLevels = levels;
    };

    vm.onSelectAWCs = function($item) {
        if ($item.location_id === 'all') {
            vm.selectedAWCs = [$item.location_id];
        } else if (vm.selectedAWCs.indexOf('all') !== -1) {
            vm.selectedAWCs = [$item.location_id];
        }
    };

    vm.filterYears = function (minYear) {
        vm.yearsCopy = [];
        var currentYear = new Date().getFullYear();

        for (var year = minYear; year <= currentYear; year++) {
            vm.yearsCopy.push({
                name: year,
                id: year,
            });
        }
        vm.years = vm.yearsCopy;
    };

    vm.onSelectYear = function (year) {
        var date = new Date();
        var latest = date;
        if (vm.isIncentiveReportSelected()) {
            var offset = date.getDate() < 15 ? 2 : 1;
            latest.setMonth(date.getMonth() - offset);
        }

        if (year.id > latest.getFullYear()) {
            vm.years =  _.filter(vm.yearsCopy, function (y) {
                return y.id <= latest.getFullYear();
            });
            vm.selectedYear = latest.getFullYear();
            vm.selectedMonth = 12;
        } else if (year.id < latest.getFullYear()) {
            vm.years =  _.filter(vm.yearsCopy, function (y) {
                return y.id <= latest.getFullYear();
            });
        }

        if (year.id === 2019 && vm.isTakeHomeRationReportSelected()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                var currentMonth = latest.getMonth() + 1;
                return month.id >= 7 && month.id <= currentMonth;
            });
            vm.selectedMonth = vm.selectedMonth >= 7 ? vm.selectedMonth : 7;
        } else if (year.id === latest.getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id <= latest.getMonth() + 1;
            });
            vm.selectedMonth = vm.selectedMonth <= latest.getMonth() + 1 ? vm.selectedMonth : latest.getMonth() + 1;
        } else if (year.id === 2017) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 3;
            });
            vm.selectedMonth = vm.selectedMonth >= 3 ? vm.selectedMonth : 3;
        } else {
            vm.months = vm.monthsCopy;
        }
    };

    vm.getAwcs = function () {
        vm.myPromise = locationsService.getAncestors();
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
            var date = new Date();
            vm.selectedYear = date.getFullYear();
            if (vm.isTakeHomeRationReportSelected()) {
                vm.selectedLevel = 5;
                vm.filterYears(vm.selectedYear);
            } else {
                vm.selectedLevel = 1;
                vm.filterYears(vm.selectedYear);
            }
            vm.onSelectYear({'id': vm.selectedYear});
            vm.selectedFormat = 'xlsx';
        }
    };

    vm.submitForm = function(csrfToken) {
        $rootScope.report_link = '';
        var awcs = vm.selectedPDFFormat === 'one' ? ['all'] : vm.selectedAWCs;
        var taskConfig = {
            'csrfmiddlewaretoken': csrfToken,
            'location': vm.selectedLocationId,
            'aggregation_level': vm.selectedLevel,
            'month': vm.selectedMonth,
            'year': vm.selectedYear,
            'indicator': vm.selectedIndicator,
            'format': vm.selectedFormat,
            'pdfformat': vm.selectedPDFFormat,
            'selected_awcs': awcs.join(','),
        };
        var selectedFilters = vm.selectedFilterOptions();
        if (vm.isChildBeneficiaryListSelected()) {
            taskConfig['filter[]'] = [];
            for (var i=0, len=selectedFilters.length; i < len; i++) {
                taskConfig['filter[]'].push(selectedFilters[i].id);
            }
        }

        downloadService.createTask(taskConfig).then(function(data) {
            vm.task_id = data.task_id;
            if (vm.task_id) {
                $rootScope.task_id = vm.task_id;
                $location.search('task_id', null);
                vm.statusCheck = setInterval(getTaskStatus, 5 * 1000);
            }
        });
        vm.queuedTask = true;
        vm.downloaded = false;
        vm.previousTaskFailed = null;
    };

    vm.resetForm = function() {
        vm.hierarchy = [];
        vm.selectedLocations = [];
        vm.selectedLocationId = userLocationId;
        vm.selectedLevel = 1;
        vm.selectedMonth = new Date().getMonth() + 1;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedIndicator = 1;
        vm.selectedFormat = 'xlsx';
        vm.selectedPDFFormat = 'many';
        initHierarchy();
    };

    vm.hasErrors = function() {
        var beneficiaryListErrors = vm.isChildBeneficiaryListSelected() && (vm.selectedFilterOptions().length === 0 || !vm.isDistrictOrBelowSelected());
        var incentiveReportErrors = vm.isIncentiveReportSelected() && !vm.isStateSelected();
        var ladySupervisorReportErrors = vm.isLadySupervisorSelected() && !vm.isStateSelected();
        return beneficiaryListErrors || incentiveReportErrors || ladySupervisorReportErrors;
    };

    vm.isCombinedPDFSelected = function() {
        return vm.isISSNIPMonthlyRegisterSelected() && vm.selectedPDFFormat === 'one';
    };

    vm.isBlockOrBelowSelected = function () {
        return vm.selectedLocations[2] && vm.selectedLocations[2] !== ALL_OPTION.location_id;
    };

    vm.isStateOrBelowSelected = function () {
        return vm.selectedLocations[0] && vm.selectedLocations[0] !== ALL_OPTION.location_id;
    };

    vm.hasErrorsISSNIPExport = function() {
        if (vm.selectedPDFFormat === 'one') {
            return vm.isISSNIPMonthlyRegisterSelected() && !vm.isBlockOrBelowSelected();
        }
        return vm.isISSNIPMonthlyRegisterSelected() && (!vm.isBlockOrBelowSelected() || !vm.isAWCsSelected());
    };

    vm.isVisible = function(level) {
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all') &&
            !(vm.isIncentiveReportSelected() && level > 2) && !(vm.isLadySupervisorSelected() && level > 2) &&
            !(vm.isTakeHomeRationReportSelected() && level > 3);
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

    vm.isIncentiveReportSelected = function () {
        return vm.selectedIndicator === 8;
    };

    vm.isLadySupervisorSelected = function () {
        return vm.selectedIndicator === 9;
    };

    vm.isTakeHomeRationReportSelected = function () {
        return vm.selectedIndicator === 10;
    };

    vm.isSupervisorOrBelowSelected = function () {
        return vm.selectedLocations[3] && vm.selectedLocations[3] !== ALL_OPTION.location_id;
    };
    
    vm.isBlockSelected = function () {
        return vm.isBlockOrBelowSelected() && !vm.isSupervisorOrBelowSelected();
    };

    vm.isStateSelected = function () {
        return vm.isStateOrBelowSelected() && !vm.isSupervisorOrBelowSelected();
    };

    vm.showViewBy = function () {
        return !(vm.isChildBeneficiaryListSelected() || vm.isIncentiveReportSelected() ||
            vm.isLadySupervisorSelected());
    };

    vm.isDistrictOrBelowSelected = function() {
        return vm.selectedLocations[1] && vm.selectedLocations[1] !== ALL_OPTION.location_id;
    };

    vm.isAWCsSelected = function() {
        return vm.selectedAWCs.length > 0;
    };

    vm.showProgressBar = function () {
        return $rootScope.task_id;
    };

    vm.readyToDownload = function () {
        return vm.previousTaskFailed ? false : $rootScope.report_link;
    };

    vm.goToLink = function () {
        if (vm.readyToDownload()) {
            window.open($rootScope.report_link);
            vm.downloaded = true;
            $rootScope.report_link = '';
        }
    };

}

DownloadController.$inject = ['$rootScope', '$location', 'locationHierarchy', 'locationsService', 'userLocationId',
    'haveAccessToFeatures', 'downloadService'];

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
