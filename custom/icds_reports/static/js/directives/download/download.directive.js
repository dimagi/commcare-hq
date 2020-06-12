/* global moment */

function DownloadController($scope, $rootScope, $location, locationHierarchy, locationsService, userLocationId, haveAccessToFeatures,
    downloadService, isAlertActive, userLocationType, haveAccessToAllLocations, allUserLocationId) {
    var vm = this;

    vm.months = [];
    vm.monthsCopy = [];
    vm.years = [];
    vm.yearsCopy = [];
    vm.quartersCopy = [];
    vm.userLocationType = userLocationType;
    vm.task_id = $location.search()['task_id'] || '';
    vm.haveAccessToFeatures = haveAccessToFeatures;
    vm.previousTaskFailed = null;
    $rootScope.report_link = '';
    vm.isAlertActive = isAlertActive;
    vm.allFiltersSelected = false;

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

    vm.updateSelectedDate = function () {
        vm.selectedDate = vm.selectedMonth ? new Date(vm.selectedYear, vm.selectedMonth - 1) : new Date();
    };

    vm.updateSelectedDate();

    window.angular.forEach(moment.months(), function (key, value) {
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

    //if report is requested in first three days of the month, then we will remove the current month in filter
    vm.excludeCurrentMonthIfInitialThreeDays = function () {
        var latest = new Date();
        if (latest.getDate() <= 3 && vm.months[vm.months.length - 1].id === latest.getMonth() + 1 &&
            vm.selectedYear === latest.getFullYear()) {
            if (vm.months.length === 1) {
                // For January, reset to Dec last year
                vm.months = vm.monthsCopy;
                vm.selectedYear = latest.getFullYear() - 1;
            } else {
                vm.months.pop();
            }
            vm.selectedMonth = vm.months[vm.months.length - 1].id;
        }
        vm.updateSelectedDate();
    };

    vm.excludeCurrentMonthIfInitialThreeDays();

    for (var year = 2017; year <= new Date().getFullYear(); year++) {
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
            new Date().getFullYear() === vm.selectedYear && !vm.isDashboardUsageSelected()
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
        {id: 6, name: 'Child Growth Monitoring List'},
        {id: 7, name: 'ICDS-CAS Monthly Register'},
        {id: 8, name: 'AWW Performance Report'},
        {id: 9, name: 'LS Performance Report'},
        {id: 10, name: 'Take Home Ration (THR)'},
    ];

    if (vm.userLocationType.toLowerCase() !== 'block') {
        vm.indicators.push({id: 11, name: 'Dashboard Activity Report'});
    }

    if (haveAccessToFeatures) {
        vm.indicators.push({id: 12, name: 'Service Delivery Report'});
        vm.indicators.push({id: 13, name: 'Child Growth Tracking Report'});
        vm.indicators.push({id: 14, name: 'AWW Activity Report'});
        vm.indicators.push({id: 15, name: 'Poshan Progress Report'});
        vm.reportLayouts = [
            {id: 'comprehensive', name: 'Comprehensive'},
            {id: 'summary', name: 'Summary'},
        ];
        vm.dataPeriods = [
            {id: 'month', name: 'Monthly'},
            {id: 'quarter', name: 'Quarterly'},
        ];
        vm.beneficiaryCategories = [
            {id: 'pw_lw_children', name: 'PW, LW & Children 0-3 years'},
            {id: 'children_3_6', name: 'Children 3-6 years'},
        ];
        vm.quarters = [
            {id: 1, name: 'Jan-Mar'},
            {id: 2, name: 'Apr-Jun'},
            {id: 3, name: 'Jul-Sep'},
            {id: 4, name: 'Oct-Dec'},
        ];
        vm.quartersCopy = vm.quarters;
        vm.selectedBeneficiaryCategory = 'pw_lw_children';
        vm.selectedReportLayout = 'comprehensive';
        vm.selectedDataPeriod = 'month';
        vm.selectedQuarter = 1;
    }
    vm.THRreportTypes = [
        {id: 'consolidated', name: 'Consolidated'},
        {id: 'beneficiary_wise', name: 'Beneficiary wise'},
        {id: 'days_beneficiary_wise', name: 'Days & Beneficiary wise'},
    ];
    vm.selectedTHRreportType = 'consolidated';
    var ALL_OPTION = locationsService.ALL_OPTION;
    var NATIONAL_OPTION = locationsService.ALL_OPTION;

    var locationsCache = {};

    vm.hierarchy = [];
    vm.selectedLocations = [];

    vm.maxLevel = 0;

    var initHierarchy = function () {
        hierarchyData = locationsService.initHierarchy(locationHierarchy);
        vm.maxLevel = hierarchyData['levels'];
        vm.selectedLocations = new Array(vm.maxLevel);
        vm.hierarchy = hierarchyData['hierarchy'];
    };

    vm.userHaveAccessToAllLocations = function (locations) {
        var haveAccessToAllLocationsForLevel = true;
        window.angular.forEach(locations, function (location) {
            if (!location.user_have_access) {
                haveAccessToAllLocationsForLevel = false;
            }
        });
        return haveAccessToAllLocationsForLevel;
    };

    vm.userLocationIdIsNull = function () {
        return ["null", "undefined"].indexOf(vm.userLocationId) !== -1;
    };

    vm.isUserLocationIn = function (locations) {
        var userLocationInSorted = _.filter(locations, function (location) {
            return allUserLocationId.indexOf(location.location_id) !== -1;
        });
        return userLocationInSorted.length > 0;
    };

    vm.preventShowingAllOption = function (locations) {
        return ((!vm.userLocationIdIsNull() && !vm.userHaveAccessToAllLocations(locations)) || vm.isUserLocationIn(locations)) && !haveAccessToAllLocations;
    };

    var init = function () {
        initHierarchy();
        locationsCache = locationsService.initLocations(vm, locationsCache);
    };

    init();

    vm.disallowNational = function () {
        return vm.isChildBeneficiaryListSelected() || vm.isChildGrowthTrackerSelected();
    };

    vm.getPlaceholder = function (locationTypes) {
        return locationsService.getLocationPlaceholder(locationTypes, vm.disallowNational());
    };

    vm.getLocationsForLevel = function (level) {
        return locationsService.getLocations(level, locationsCache, vm.selectedLocations, vm.disallowNational());
    };

    vm.disabled = function (level) {
        return locationsService.isLocationDisabled(level, vm);
    };

    vm.onSelectForISSNIP = function ($item, level) {
        var selectedLocIndex = locationsService.selectedLocationIndex(vm.selectedLocations);
        var selectedLocationId = vm.selectedLocations[selectedLocIndex];
        vm.locationPromise = locationsService.getAwcLocations(selectedLocationId).then(function (data) {
            if ($item.user_have_access) {
                vm.awcLocations = [ALL_OPTION].concat(data);
            } else {
                vm.awcLocations = data;
            }
        });
        vm.selectedAWCs = [];
        vm.onSelectLocation($item, level);
    };

    vm.onSelectLocation = function ($item, level) {
        locationsService.onSelectLocation($item, level, locationsCache, vm);
    };

    vm.onSelectAWCs = function ($item) {
        if ($item.location_id === 'all') {
            vm.selectedAWCs = [$item.location_id];
        } else if (vm.selectedAWCs.indexOf('all') !== -1) {
            vm.selectedAWCs = [$item.location_id];
        }
    };

    vm.onSelectMonth = function () {
        vm.updateSelectedDate();
    };

    vm.onSelectYear = function (year) {
        var date = new Date();
        var latest = date;
        vm.years = vm.yearsCopy;
        vm.months = vm.monthsCopy;

        if (vm.isIncentiveReportSelected()) {
            vm.years = _.filter(vm.yearsCopy, function (y) {
                return y.id >= 2018;
            });
            vm.setAvailableAndSelectedMonthForAWWPerformanceReport();
            return;
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

        if (vm.isSDRSelected()) {
            vm.years = _.filter(vm.yearsCopy, function (y) {
                return y.id >= 2020;
            });
        }

        if (vm.isTakeHomeRationReportSelected()) {
            vm.years = _.filter(vm.yearsCopy, function (y) {
                return y.id >= 2019;
            });
        }

        if (year.id === 2019 && vm.isTakeHomeRationReportSelected()) {
            var currentMonth = latest.getMonth() + 1;
            var currentYear = latest.getFullYear();
            vm.months = _.filter(vm.monthsCopy, function (month) {
                if (currentYear === 2019) {
                    return month.id >= 7 && month.id <= currentMonth;
                } else {
                    return month.id >= 7;
                }
            });
            vm.selectedMonth = vm.selectedMonth >= 7 ? vm.selectedMonth : 7;
        } else if((year.id === 2019 && vm.isPPRSelected())) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                    return month.id >= 4
            });
            vm.selectedMonth = vm.selectedMonth >= 4 ? vm.selectedMonth : 4;
            vm.quarters = vm.quartersCopy.slice(1,4);
            vm.selectedQuarter = vm.selectedQuarter >= 2 ? vm.selectedQuarter : 2;

        } else if (year.id === latest.getFullYear()) {
            const maxQuarter = Math.floor((latest.getMonth() + 1)/4);
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id <= latest.getMonth() + 1;
            });
            vm.selectedMonth = vm.selectedMonth <= latest.getMonth() + 1 ? vm.selectedMonth : latest.getMonth() + 1;
            vm.quarters = _.filter(vm.quartersCopy, function (quarter) {
                return quarter.id <= maxQuarter;
            });
            vm.selectedQuarter = vm.selectedQuarter <= maxQuarter ? vm.selectedQuarter : maxQuarter;

        } else if (year.id === 2017) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 3;
            });
            vm.selectedMonth = vm.selectedMonth >= 3 ? vm.selectedMonth : 3;
        } else {
            vm.months = vm.monthsCopy;
            vm.quarters = v.quartersCopy;
        }
        vm.excludeCurrentMonthIfInitialThreeDays();
    };

    //if selected year is 2018 make only months from october selectable as the report is only available from october 2018
    vm.setAvailableAndSelectedMonthForAWWPerformanceReport = function () {
        var today = new Date();
        if (vm.selectedYear === today.getFullYear()) {
            vm.setMonthToPreviousIfAfterThe15thAndTwoMonthsIfBefore15th(today);

            if (vm.selectedMonth > vm.months[0].id) {
                vm.selectedMonth = vm.months[0].id;
            }
        } else if (vm.selectedYear === 2018) {
            vm.months = vm.months.slice(-3);
            if (vm.selectedMonth < 10) {
                vm.selectedMonth = 10;
            }
        }
        vm.updateSelectedDate();
    };

    vm.setMonthToPreviousIfAfterThe15thAndTwoMonthsIfBefore15th = function (date) {
        var offset = date.getDate() < 15 ? 2 : 1;

        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id <= (date.getMonth() + 1) - offset;
        });
    };

    vm.getAwcs = function () {
        vm.locationPromise = locationsService.getAncestors();
    };

    vm.getFormats = function () {
        if (vm.isChildBeneficiaryListSelected()) {
            return [vm.formats[0]];
        } else {
            return vm.formats;
        }
    };

    vm.onIndicatorSelect = function () {
        if (vm.isChildBeneficiaryListSelected()) {
            init();
            vm.selectedFormat = vm.formats[0].id;
        } else if (vm.isIncentiveReportSelected()) {
            // if current selected year is less than 2018,
            // change the selected year to latest as the report is not available before 2018
            if (vm.selectedYear < 2018) {
                vm.selectedYear = new Date().getFullYear();
            }
            vm.onSelectYear({'id': vm.selectedYear});
        } else {
            if (vm.isTakeHomeRationReportSelected()) {
                var currentYear  = new Date().getFullYear();
                vm.selectedYear = vm.selectedYear >= 2019 ? vm.selectedYear : currentYear;
                locationsService.resetLevelsBelow(3, vm);
            } else if (vm.isSDRSelected()) {
                if (vm.selectedYear < 2020) {
                    vm.selectedYear = new Date().getFullYear();
                }
            } else if (vm.isPPRSelected()) {
                var currentYear  = new Date().getFullYear();
                vm.selectedYear = vm.selectedYear >= 2019 ? vm.selectedYear : currentYear;
                if (vm.selectedYear == currentYear) {
                    if ([0, 1, 2].includes(new Date().getMonth())) {
                        vm.selectedYear = currentYear - 1;
                        vm.years = _.filter(vm.yearsCopy, function (year) {
                            return year.id >= 2019 && year.id < currentYear;
                        });
                    } else {
                        vm.selectedYear = currentYear;
                        vm.years = _.filter(vm.yearsCopy, function (year) {
                            return year.id >= 2019;
                        });
                    }
                }
                vm.selectedFormat = vm.formats[1].id;

            } else {
                vm.years = vm.yearsCopy;
            }
            vm.onSelectYear({'id': vm.selectedYear});
            vm.selectedFormat = 'xlsx';
        }
        // set data period to monthly for all
        vm.selectedDataPeriod = 'month'
        vm.adjustSelectedLevelForNoViewByFilter();


    };

    /**
     * To adjust selectedLevel for the reports that do not have viewBy filter. These
     * reports end up having selectedLevel set by viewBy filter in the last report selected.
     */
    vm.adjustSelectedLevelForNoViewByFilter = function () {
        if (!vm.showViewBy()) {
            vm.selectedLevel = locationsService.selectedLocationIndex(vm.selectedLocations) + 1;
        }
    };
    vm.submitForm = function (csrfToken) {
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
        if (haveAccessToFeatures) {
            taskConfig['beneficiary_category'] = vm.selectedBeneficiaryCategory;
            taskConfig['thr_report_type'] = vm.selectedTHRreportType;
            taskConfig['report_layout'] = vm.selectedReportLayout;
            taskConfig['data_period'] = vm.selectedDataPeriod;
            taskConfig['quarter'] = vm.selectedQuarter;
        }
        var selectedFilters = vm.selectedFilterOptions();
        if (vm.isChildBeneficiaryListSelected()) {
            taskConfig['filter[]'] = [];
            for (var i = 0, len = selectedFilters.length; i < len; i++) {
                taskConfig['filter[]'].push(selectedFilters[i].id);
            }
        }

        downloadService.createTask(taskConfig).then(function (data) {
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

    vm.resetForm = function () {
        vm.hierarchy = [];
        vm.selectedLocations = [];
        vm.selectedLocationId = userLocationId;
        vm.selectedLevel = 1;
        vm.selectedMonth = new Date().getMonth() + 1;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedIndicator = 1;
        vm.selectedFormat = 'xlsx';
        vm.selectedPDFFormat = 'many';
        vm.selectedQuarter = 1;
        vm.selectedDataPeriod = 'month';
        initHierarchy();
        vm.updateSelectedDate();
    };

    vm.hasErrors = function () {
        var beneficiaryListErrors = vm.isChildBeneficiaryListSelected() && (vm.selectedFilterOptions().length === 0 || !vm.isDistrictOrBelowSelected());
        var growthListErrors = vm.isChildGrowthTrackerSelected() && !vm.isDistrictOrBelowSelected();
        var incentiveReportErrors = vm.isIncentiveReportSelected() && !vm.isStateSelected();
        var PPRErrors = vm.isPPRSelected() && vm.isDistrictOrBelowSelected();
        var ladySupervisorReportErrors = false;
        if (!vm.haveAccessToFeatures) {
            ladySupervisorReportErrors = vm.isLadySupervisorSelected() && !vm.isStateSelected();
        }
        var awwActvityReportErrors = vm.isAwwActivityReportSelected() && !vm.isStateSelected();
        return beneficiaryListErrors || incentiveReportErrors || ladySupervisorReportErrors || growthListErrors || awwActvityReportErrors || PPRErrors;
    };

    vm.isCombinedPDFSelected = function () {
        return vm.isISSNIPMonthlyRegisterSelected() && vm.selectedPDFFormat === 'one';
    };

    vm.isBlockOrBelowSelected = function () {
        return vm.selectedLocations[2] && vm.selectedLocations[2] !== ALL_OPTION.location_id;
    };

    vm.isStateOrBelowSelected = function () {
        return vm.selectedLocations[0] && vm.selectedLocations[0] !== ALL_OPTION.location_id;
    };

    vm.hasErrorsISSNIPExport = function () {
        if (vm.selectedPDFFormat === 'one') {
            return vm.isISSNIPMonthlyRegisterSelected() && !vm.isBlockOrBelowSelected();
        }
        return vm.isISSNIPMonthlyRegisterSelected() && (!vm.isBlockOrBelowSelected() || !vm.isAWCsSelected());
    };

    vm.isVisible = function (level) {
        return level === 0 || (vm.selectedLocations[level - 1] && vm.selectedLocations[level - 1] !== 'all') &&
            !(vm.isIncentiveReportSelected() && level > 2) && !(vm.isLadySupervisorSelected() && level > 2) &&
            !(vm.isTakeHomeRationReportSelected() && level > 3);
    };

    vm.selectedFilterOptions = function () {
        return vm.filterOptions.filter(function (el) {
            return el.selected;
        });
    };

    vm.selectAllFilters = function () {
        var allSelected = document.getElementById('selectAll').checked;
        for (var i = 0; i < vm.filterOptions.length; i++) {
            vm.filterOptions[i].selected = allSelected;
        }
        vm.allFiltersSelected = allSelected;
    };

    $scope.$watch(function () {
        return vm.filterOptions;
    }, function () {
        vm.allFiltersSelected = (vm.selectedFilterOptions().length === vm.filterOptions.length);
    }, true);

    vm.isChildBeneficiaryListSelected = function () {
        return vm.selectedIndicator === 6;
    };

    vm.isSDRSelected = function () {
        return vm.selectedIndicator === 12;
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

    vm.isDashboardUsageSelected = function () {
        return vm.selectedIndicator === 11;
    };

    vm.isChildGrowthTrackerSelected = function () {
        return vm.selectedIndicator === 13;
    };

    vm.isMonthlyDataPeriodSelected = function() {
        return vm.selectedDataPeriod === 'month';
    };

    vm.isQuarterDataPeriodSelected = function() {
        return vm.selectedDataPeriod === 'quarter';
    };

    vm.isPPRSelected = function() {
        return vm.selectedIndicator === 15;
    };

    vm.isAwwActivityReportSelected = function () {
        return vm.selectedIndicator === 14;
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
            vm.isLadySupervisorSelected() || vm.isDashboardUsageSelected() ||
            vm.isChildGrowthTrackerSelected() || vm.isTakeHomeRationReportSelected() || vm.isAwwActivityReportSelected());
    };

    vm.showLocationFilter = function () {
        return !vm.isDashboardUsageSelected();
    };

    vm.showMonthFilter = function () {
        return !(vm.isDashboardUsageSelected() || vm.isAwwActivityReportSelected() || vm.isQuarterDataPeriodSelected());
    };

    vm.showQuarterFilter = function() {
        return !vm.isDashboardUsageSelected() && vm.isQuarterDataPeriodSelected();
    }

    vm.showYearFilter = function () {
        return !(vm.isDashboardUsageSelected() || vm.isAwwActivityReportSelected());
    };


    vm.isDistrictOrBelowSelected = function () {
        return vm.selectedLocations[1] && vm.selectedLocations[1] !== ALL_OPTION.location_id;
    };

    vm.isAWCsSelected = function () {
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

    vm.showReassignmentMessage = function () {
        var utcSelectedDate = Date.UTC(vm.selectedDate.getFullYear(), vm.selectedDate.getMonth());
        return vm.selectedLocation && (Date.parse(vm.selectedLocation.archived_on) <= utcSelectedDate || Date.parse(vm.selectedLocation.deprecates_at) > utcSelectedDate);
    };
}

DownloadController.$inject = ['$scope', '$rootScope', '$location', 'locationHierarchy', 'locationsService',
    'userLocationId', 'haveAccessToFeatures', 'downloadService', 'isAlertActive', 'userLocationType',
    'haveAccessToAllLocations','allUserLocationId'];

window.angular.module('icdsApp').directive("download", function () {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'download.directive'),
        controller: DownloadController,
        controllerAs: "$ctrl",
    };
});
