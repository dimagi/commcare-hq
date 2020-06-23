var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ServiceDeliveryDashboardController($rootScope, $scope, $http, $location, $routeParams, $log, DTOptionsBuilder,
                                            DTColumnBuilder, $compile, storageService, userLocationId,
                                            baseControllersService, haveAccessToAllLocations, isAlertActive,
                                            sddMetadata, dateHelperService, navigationService, isMobile,
                                            haveAccessToFeatures) {
    baseControllersService.BaseFilterController.call(
        this, $scope, $routeParams, $location, dateHelperService, storageService, navigationService
    );
    var vm = this;
    vm.haveAccessToFeatures = haveAccessToFeatures;
    vm.data = {};
    vm.label = "Service Delivery Dashboard";
    vm.haveAccessToAllLocations = haveAccessToAllLocations;
    vm.tooltipPlacement = "right";
    vm.filters = ['gender', 'age', 'data_period'];
    vm.userLocationId = userLocationId;
    vm.dataNotEntered = "Data Not Entered";
    vm.showTable = true;
    vm.dataAggregationLevel = 1;
    vm.isAlertActive = isAlertActive;

    vm.isCbeSeeMoreDisplayed = true;
    vm.isTHRSeeMoreDisplayed = true;
    vm.isSNSeeMoreDisplayed = true;
    vm.isPSESeeMoreDisplayed = true;

    vm.totalNumberOfEntries = 0; // total number of records in table
    vm.selectedDate = dateHelperService.getSelectedDate();

    vm.sddStartDate = dateHelperService.getReportStartDates()['sdd'];

    vm.showMessage = $rootScope.dateChanged;
    $rootScope.dateChanged = false;

    function _getStep(stepId) {
        return {
            "id": stepId,
            "route": "/service_delivery_dashboard/" + stepId,
            "label": sddMetadata[stepId]["label"],
            "image": sddMetadata[stepId]["image"],
        };
    }
    vm.steps = {
        "pw_lw_children": _getStep("pw_lw_children"),
        "children": _getStep("children"),
    };

    vm.step = $routeParams.step;
    vm.currentStepMeta = vm.steps[vm.step];

    vm.isDetailsDisplayed = (vm.step === 'cbe' || vm.step === 'thr' ||
        vm.step === 'sn' || vm.step === 'pse') && haveAccessToFeatures;

    if (vm.isDetailsDisplayed) {
        if (vm.step === 'cbe') {
            vm.detailsTableHeading = 'COMMUNITY BASED EVENTS';
        } else if (vm.step === 'thr') {
            vm.detailsTableHeading = 'TAKE HOME RATION';
        } else if (vm.step === 'sn') {
            vm.detailsTableHeading = 'SUPPLEMENTARY NUTRITION';
        } else if (vm.step === 'pse') {
            vm.detailsTableHeading = 'PRE-SCHOOL EDUCATION';
        }
    }

    vm.closeDetails = function() {
        if (vm.step === 'cbe' || vm.step === 'thr') {
            $location.path('/service_delivery_dashboard/pw_lw_children');
        } else if (vm.step === 'sn' || vm.step === 'pse') {
            $location.path('/service_delivery_dashboard/children');
        }
    };

    vm.displaySeeMore = function (detailsUrl) {
        if (detailsUrl === '/service_delivery_dashboard/cbe') {
            return vm.isCbeSeeMoreDisplayed;
        } else if (detailsUrl === '/service_delivery_dashboard/thr') {
            return vm.isTHRSeeMoreDisplayed;
        } else if (detailsUrl === '/service_delivery_dashboard/sn') {
            return vm.isSNSeeMoreDisplayed;
        } else if (detailsUrl === '/service_delivery_dashboard/pse') {
            return vm.isPSESeeMoreDisplayed;
        }
    };

    vm.dtOptions = DTOptionsBuilder.newOptions()
        .withOption('ajax', {
            url: url(vm.isDetailsDisplayed ? 'service_delivery_dashboard_details' : 'service_delivery_dashboard', vm.step),
            data: $location.search(),
            type: 'GET',
        })
        .withDataProp('data')
        .withOption('processing', true)
        .withOption('serverSide', true)
        .withOption('createdRow', compile)
        .withPaginationType('full_numbers')
        .withFixedHeader({
            bottom: true,
        })
        .withOption('oLanguage', {
            "sProcessing": "Loading. Please wait...",
        })
        .withOption('order', [[0, 'asc']])
        .withDOM('ltipr')
        .withOption('initComplete', function() {
             $compile(angular.element('thead').contents())($scope);
        });

    vm.getLocationLevelNameAndField = function () {
        var locationLevelName = 'State';
        var locationLevelNameField = 'state_name';
        if (vm.dataAggregationLevel === 1) {
            locationLevelName = 'State';
            locationLevelNameField = 'state_name';
        } else if (vm.dataAggregationLevel === 2) {
            locationLevelName = 'District';
            locationLevelNameField = 'district_name';
        } else if (vm.dataAggregationLevel === 3) {
            locationLevelName = 'Block';
            locationLevelNameField = 'block_name';
        } else if (vm.dataAggregationLevel === 4) {
            locationLevelName = 'Sector';
            locationLevelNameField = 'supervisor_name';
        } else {
            locationLevelName = 'AWC';
            locationLevelNameField = 'awc_name';
        }
        return {
            'locationLevelName': locationLevelName,
            'locationLevelNameField': locationLevelNameField,
        };
    };

    vm.sddTableData = {
        'pw_lw_children': {
            'non-awc': [
                {
                    'mData': 'num_launched_awcs',
                    'heading': 'Number of AWCs launched',
                    'tooltipValue': 'Total Number of Anganwadi Centers launched in the selected location.',
                    'columnValueType': 'raw',
                    'columnValueIndicator': 'num_launched_awcs',
                },
                {
                    'mData': 'home_visits',
                    'heading': 'Home Visits',
                    'tooltipValue': 'Of the total number of expected home visits, the percentage of home visits completed by AWW.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'homeVisits',
                },
                {
                    'mData': 'gm',
                    'heading': 'Growth Monitoring',
                    'tooltipValue': 'Of the total children between 0-3 years of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'gm03',
                },
                {
                    'mData': 'num_awcs_conducted_cbe',
                    'heading': 'Community Based Events',
                    'tooltipValue': 'Of the total number of launched Anganwadi Centers, the percentage who have conducted at least 2 Community Based Events in the given month.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'num_awcs_conducted_cbe',
                    'detailsURL': '/service_delivery_dashboard/cbe',
                },
                {
                    'mData': 'num_awcs_conducted_vhnd',
                    'heading': 'VHSND',
                    'tooltipValue': 'Total number of Anganwadi Centers who have conducted at least 1 Village, Health, Sanitation and Nutrition Day in the given month.',
                    'columnValueType': 'raw',
                    'columnValueIndicator': 'num_awcs_conducted_vhnd',
                },
                {
                    'mData': 'thr',
                    'heading': 'Take Home Ration (21+ days)',
                    'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) and 6-36 months children who were provided THR for at least 21 days in the current month.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'thr',
                    'detailsURL': '/service_delivery_dashboard/thr',
                },
            ],
            'awc': [
                {
                    'mData': 'home_visits',
                    'heading': 'Home Visits',
                    'tooltipValue': 'Of the total number of expected home visits, the percentage of home visits completed by AWW.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'homeVisits',
                },
                {
                    'mData': 'gm',
                    'heading': 'Growth Monitoring',
                    'tooltipValue': 'Of the total children between 0-3 years of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'gm03',
                },
                {
                    'mData': 'num_awcs_conducted_cbe',
                    'heading': 'Community Based Events',
                    'tooltipValue': 'If the AWC conducted at least 2 CBE in the current month then Yes otherwise No.',
                    'columnValueType': 'booleanRaw',
                    'columnValueIndicator': 'num_awcs_conducted_cbe',
                    'detailsURL': '/service_delivery_dashboard/cbe',
                },
                {
                    'mData': 'num_awcs_conducted_vhnd',
                    'heading': 'VHSND',
                    'tooltipValue': 'If the AWC conducted at least 1 VHSND in the current month then Yes otherwise No.',
                    'columnValueType': 'booleanRaw',
                    'columnValueIndicator': 'num_awcs_conducted_vhnd',
                },
                {
                    'mData': 'thr',
                    'heading': 'Take Home Ration (21+ days)',
                    'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) and 6-36 months children who were provided THR for at least 21 days in the current month.',
                    'columnValueType': 'percentage',
                    'columnValueIndicator': 'thr',
                    'detailsURL': '/service_delivery_dashboard/thr',
                },
            ],
        },
        'children': [
            {
                'mData': 'sn',
                'heading': 'Supplementary Nutrition (21+ days)',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal i.e. supplementary nutrition for at least 21 days in the current month.',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'supNutrition',
                'detailsURL': '/service_delivery_dashboard/sn',
            },
            {
                'mData': 'pse',
                'heading': 'Pre-school Education (21+ days)',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 21 days in the current month.',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse',
                'detailsURL': '/service_delivery_dashboard/pse',
            },
            {
                'mData': 'gm',
                'heading': 'Growth Monitoring',
                'tooltipValue': 'Of the total children between <b>3-5 years</b> of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.<br><br><b>Growth Monitoring is done only for children till 5 years of age.</b>',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'gm36',
            },
        ],
        'pse': [
            {
                'mData': 'pse_0_days_val',
                'heading': 'Not attended',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who did not attend Pre-school education in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse0',
            },
            {
                'mData': 'pse_1_7_days_val',
                'heading': 'Attended for (1-7) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for 1-7 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse17',
            },
            {
                'mData': 'pse_8_14_days_val',
                'heading': 'Attended for (8-14) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for 8-14 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse814',
            },
            {
                'mData': 'pse_15_20_days_val',
                'heading': 'Attended for (15-20) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for 15-20 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse1520',
            },
            {
                'mData': 'pse_21_24_days_val',
                'heading': 'Attended for (21-24) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for 21-24 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse2124',
            },
            {
                'mData': 'pse_25_days_val',
                'heading': 'Attended for at least 25 days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 25 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse25',
            },
        ],
        'sn': [
            {
                'mData': 'lunch_0_days_val',
                'heading': 'Not Provided',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were not provided Hot Cooked Meal, i.e., supplementary nutrition',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch0',
            },
            {
                'mData': 'lunch_1_7_days_val',
                'heading': 'Provided for (1-7) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal, i.e., supplementary nutrition for 1-7 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch17',
            },
            {
                'mData': 'lunch_8_14_days_val',
                'heading': 'Provided for (8-14) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal, i.e., supplementary nutrition for 8-14 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch814',
            },
            {
                'mData': 'lunch_15_20_days_val',
                'heading': 'Provided for (15-20) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal, i.e., supplementary nutrition for 15-20 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch1520',
            },
            {
                'mData': 'lunch_21_24_days_val',
                'heading': 'Provided for (21-24) days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal, i.e., supplementary nutrition for 21-24 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch2124',
            },
            {
                'mData': 'lunch_25_days_val',
                'heading': 'Provided for at least 25 days',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal, i.e., supplementary nutrition for at least 25 days in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'lunch25',
            },
        ],
        'thr': [
            {
                'mData': 'thr_0_days_val',
                'heading': 'Not Distributed',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children)  who were not provided with THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr0',
            },
            {
                'mData': 'thr_1_7_days_val',
                'heading': 'Distributed for (1-7) days',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) who were provided with 1-7 days of THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr17',
            },
            {
                'mData': 'thr_8_14_days_val',
                'heading': 'Distributed for (8-14) days',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) who were provided with 8-14 days of THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr814',
            },
            {
                'mData': 'thr_15_20_days_val',
                'heading': 'Distributed for (15-20) days',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) who were provided with 15-20 days of THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr1520',
            },
            {
                'mData': 'thr_21_24_days_val',
                'heading': 'Distributed for (21-24) days',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) who were provided with 21-24 days of THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr2124',
            },
            {
                'mData': 'thr_25_days_val',
                'heading': 'Distributed for at least 25 days',
                'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) who were provided with at least 25 days of THR in the current month',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'thr25',
            },
        ],
        'cbe': [
            {
                'mData': 'cbe_conducted',
                'heading': 'Number of CBEs conducted',
                'tooltipValue': 'Total number of Community Based Events conducted in the month',
                'columnValueType': 'raw',
                'columnValueIndicator': 'cbe_conducted',
            },
            {
                'mData': 'third_fourth_month_of_pregnancy_count',
                'heading': 'Third, Fourth month of pregnancy',
                'tooltipValue': 'Total number of community based events conducted in the month with ‘Third fourth month of pregnancy’ as the theme',
                'columnValueType': 'raw',
                'columnValueIndicator': 'third_fourth_month_of_pregnancy_count',
            },
            {
                'mData': 'annaprasan_diwas_count',
                'heading': 'Annaprasan Diwas',
                'tooltipValue': 'Total number of community based events conducted in the month with ‘Annaprasan Diwas’ as the theme',
                'columnValueType': 'raw',
                'columnValueIndicator': 'annaprasan_diwas_count',
            },
            {
                'mData': 'suposhan_diwas_count',
                'heading': 'Suposhan Diwas',
                'tooltipValue': 'Total number of community based events conducted in the month with ‘Suposhan Diwas’ as the theme',
                'columnValueType': 'raw',
                'columnValueIndicator': 'suposhan_diwas_count',
            },
            {
                'mData': 'coming_of_age_count',
                'heading': 'Celebrating Coming-of-age',
                'tooltipValue': 'Total number of community based events conducted in the month with ‘Celebrating coming-of-age’ as the theme',
                'columnValueType': 'raw',
                'columnValueIndicator': 'coming_of_age_count',
            },
            {
                'mData': 'public_health_message_count',
                'heading': 'Public Health Message',
                'tooltipValue': 'Total number of community based events conducted in the month with ‘Public Health Message’ as the theme',
                'columnValueType': 'raw',
                'columnValueIndicator': 'public_health_message_count',
            },
        ],
    };

    var thrForAtleast25Days = {
        'mData': 'thr',
        'heading': 'Take Home Ration (25+ days)',
        'tooltipValue': 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) and 6-36 months children who were provided THR for at least 25 days in the current month.',
        'columnValueType': 'percentage',
        'columnValueIndicator': 'thrAtleast25',
        'detailsURL': '/service_delivery_dashboard/thr',
    };

    var snForAtleast25Days = {
        'mData': 'sn',
        'heading': 'Supplementary Nutrition (25+ days)',
        'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal i.e. supplementary nutrition for at least 25 days in the current month.',
        'columnValueType': 'percentage',
        'columnValueIndicator': 'snAtleast25',
        'detailsURL': '/service_delivery_dashboard/sn',
    };

    var pseForAtleast25Days = {
        'mData': 'pse',
        'heading': 'Pre-school Education (25+ days)',
        'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 25 days in the current month.',
        'columnValueType': 'percentage',
        'columnValueIndicator': 'pseAtleast25',
        'detailsURL': '/service_delivery_dashboard/pse',
    };

    if (haveAccessToFeatures && vm.selectedDate >= new Date(2020, 3, 1)) {
        vm.sddTableData['pw_lw_children']['non-awc'].pop();
        vm.sddTableData['pw_lw_children']['non-awc'].push(thrForAtleast25Days);
        vm.sddTableData['pw_lw_children']['awc'].pop();
        vm.sddTableData['pw_lw_children']['awc'].push(thrForAtleast25Days);
        vm.sddTableData['children'].splice(0, 2);
        vm.sddTableData['children'].unshift(pseForAtleast25Days);
        vm.sddTableData['children'].unshift(snForAtleast25Days);
    }

    if (haveAccessToFeatures) {
        var numberOfVHSNDConducted = {
            'mData': 'vhnd_conducted',
            'heading': 'Number of VHSND conducted',
            'tooltipValue': 'Number of Village Health Sanitation and Nutrition Days (VHSNDs) organised by an AWC in a month',
            'columnValueType': 'raw',
            'columnValueIndicator': 'vhnd_conducted',
        };
        vm.sddTableData['pw_lw_children']['awc'].splice(5, 0, numberOfVHSNDConducted);
    }

    vm.getTableData = function () {
        var isPwLwChildren = vm.isPwLwChildrenTab();
        var isAwc = vm.isAwcDataShown();
        var isChildrenTab = ($location.path().indexOf('/children') !== -1);
        var isPSEDetails = ($location.path().indexOf('/pse') !== -1);
        var isSNDetails = ($location.path().indexOf('/sn') !== -1);
        var isTHRDetails = ($location.path().indexOf('/thr') !== -1);
        var isCBEDetails = ($location.path().indexOf('/cbe') !== -1);
        if (isPwLwChildren) {
            return (isAwc ? vm.sddTableData['pw_lw_children']['awc'] : vm.sddTableData['pw_lw_children']['non-awc']);
        } else if (isChildrenTab) {
            return vm.sddTableData['children'];
        } else if (isPSEDetails) {
            return vm.sddTableData['pse'];
        } else if (isSNDetails) {
            return vm.sddTableData['sn'];
        } else if (isTHRDetails) {
            return vm.sddTableData['thr'];
        } else if (isCBEDetails) {
            return vm.sddTableData['cbe'];
        }
    };

    vm.isPwLwChildrenTab = function () {
        return ($location.path().indexOf('/pw_lw_children') !== -1);
    };

    vm.isAwcDataShown = function () {
        // if sector level is selected --> selectedLocationLevel is 3
        return (parseInt(vm.selectedLocationLevel, 10) === 3);
    };

    vm.buildDataTable = function () {
        var tableData = vm.getTableData();
        var dataTableColumns = [];
        for (var i = 0; i < tableData.length; i++) {
            dataTableColumns.push(DTColumnBuilder.newColumn(tableData[i]['mData'])
                .withTitle(renderHeaderTooltip(tableData[i]['heading'], tableData[i]['tooltipValue'], tableData[i]['detailsURL'], vm.displaySeeMore(tableData[i]['detailsURL'])))
                .renderWith(renderCellValue(tableData[i]['columnValueType'],tableData[i]['columnValueIndicator']))
                .withClass('medium-col'));
        }
        return dataTableColumns;
    };

    vm.setDtColumns = function () {
        var locationLevelName = vm.getLocationLevelNameAndField()['locationLevelName'];
        var locationLevelNameField = vm.getLocationLevelNameAndField()['locationLevelNameField'];
        vm.dtColumns = [DTColumnBuilder.newColumn(
            locationLevelNameField
        ).withTitle(
            locationLevelName.toUpperCase()
        ).renderWith(renderCellValue('raw', locationLevelNameField)
        ).withClass('medium-col')];
        vm.dtColumns = vm.dtColumns.concat(vm.buildDataTable());
    };

    vm.setDtColumns();

    $scope.goToDetailsPage = function (detailsURL) {
        $location.path(detailsURL);
    }

    function compile(row) {
        $compile(window.angular.element(row).contents())($scope);
    }

    function renderHeaderTooltip(header, tooltipContent, detailsURL, displaySeeMore) {
        var seeMore = '';
        if (detailsURL && haveAccessToFeatures && displaySeeMore) {
            seeMore = '<div class="d-flex justify-content-end">' +
                '<span ng-click="goToDetailsPage(\''+ detailsURL +'\')"' +
                ' class="sdd-details-link">See more</span></div>'
        }
        return '<i class="fa fa-info-circle headerTooltip" style="float: right;" >' +
            '<div class="headerTooltipText">' + tooltipContent + '</div></i><span>' + header.toUpperCase() + '</span>' + seeMore;
    }

    function isZeroNullUnassignedOrDataNotEntered(value) {
        return value === 0 || value === null || value === void(0) || value === vm.dataNotEntered;
    }

    function renderPercentageAndPartials(percentage, numerator, denominator, indicator) {
        if (isZeroNullUnassignedOrDataNotEntered(denominator)) {
            return isMobile ? ('No expected ' + indicator) : '<div> No expected ' + indicator + ' </div>';
        }
        else {
            if (denominator === vm.dataNotEntered) {
                return vm.dataNotEntered;
            }
            if (percentage === vm.dataNotEntered) {
                if (numerator === 0 && denominator === 0) {
                    return isMobile ? ('100% (' + numerator + ' / ' + denominator + ')') :
                        '<div><span>100 %<br>(' + numerator + ' / ' + denominator + ')</span></div>';
                }
                return isMobile ? ('(' + numerator + ' / ' + denominator + ')') :
                    '<div><span>(' + numerator + ' / ' + denominator + ')</span></div>';
            }
        }

        return isMobile ? (percentage + '(' + numerator + ' / ' + denominator + ')') :
            '<div><span>' + percentage + '<br>(' + numerator + ' / ' + denominator + ')</span></div>';
    }


    function renderCellValue(CellType, indicator) {

        return function (data, type, full) {

            if (['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'num_launched_awcs'].indexOf(indicator) === -1 && isZeroNullUnassignedOrDataNotEntered(full['num_launched_awcs'])) {
                return isMobile ? 'Not Launched' : '<div>Not Launched</div>';
            }

            switch (CellType) {
                case "raw": return simpleRender(full, indicator, 'raw');
                case "booleanRaw": return simpleRender(full, indicator, 'booleanRaw');
                case "percentage":
                    switch (indicator) {
                        case "homeVisits": return renderPercentageAndPartials(full.home_visits, full.valid_visits, full.expected_visits, 'Home visits');
                        case "gm03": return  renderPercentageAndPartials(full.gm, full.gm_0_3, full.children_0_3, 'Weight measurement');
                        case "gm36": return renderPercentageAndPartials(full.gm, full.gm_3_5, full.children_3_5, 'Weight measurement');
                        case "thr": return renderPercentageAndPartials(full.thr, haveAccessToFeatures ? full.thr_21_days : full.thr_given_21_days, haveAccessToFeatures ? full.thr_eligible : full.total_thr_candidates, 'THR');
                        case "pse": return renderPercentageAndPartials(full.pse, haveAccessToFeatures ? full.pse_21_days : full.pse_attended_21_days, haveAccessToFeatures ? full.pse_eligible : full.children_3_6, 'beneficiaries');
                        case "supNutrition": return renderPercentageAndPartials(full.sn, haveAccessToFeatures ? full.lunch_21_days : full.lunch_count_21_days, haveAccessToFeatures ? full.pse_eligible : full.children_3_6, 'beneficiaries');
                        case "thrAtleast25": return renderPercentageAndPartials(full.thr, full.thr_25_days, full.thr_eligible, 'THR');
                        case "pseAtleast25": return renderPercentageAndPartials(full.pse, full.pse_25_days, full.pse_eligible, 'beneficiaries');
                        case "snAtleast25": return renderPercentageAndPartials(full.sn, full.lunch_25_days, full.pse_eligible, 'beneficiaries');
                        case "num_awcs_conducted_cbe": return renderPercentageAndPartials(full.cbe, full.num_awcs_conducted_cbe, full.num_launched_awcs, 'CBE');
                        case "pse0": return renderPercentageAndPartials(full.pse_0_days_val, full.pse_0_days, full.pse_eligible, 'beneficiaries');
                        case "pse17": return renderPercentageAndPartials(full.pse_1_7_days_val, full.pse_1_7_days, full.pse_eligible, 'beneficiaries');
                        case "pse814": return renderPercentageAndPartials(full.pse_8_14_days_val, full.pse_8_14_days, full.pse_eligible, 'beneficiaries');
                        case "pse1520": return renderPercentageAndPartials(full.pse_15_20_days_val, full.pse_15_20_days, full.pse_eligible, 'beneficiaries');
                        case "pse2124": return renderPercentageAndPartials(full.pse_21_24_days_val, full.pse_21_24_days, full.pse_eligible, 'beneficiaries');
                        case "pse25": return renderPercentageAndPartials(full.pse_25_days_val, full.pse_25_days, full.pse_eligible, 'beneficiaries');
                        case "lunch0": return renderPercentageAndPartials(full.lunch_0_days_val, full.lunch_0_days, full.pse_eligible, 'beneficiaries');
                        case "lunch17": return renderPercentageAndPartials(full.lunch_1_7_days_val, full.lunch_1_7_days, full.pse_eligible, 'beneficiaries');
                        case "lunch814": return renderPercentageAndPartials(full.lunch_8_14_days_val, full.lunch_8_14_days, full.pse_eligible, 'beneficiaries');
                        case "lunch1520": return renderPercentageAndPartials(full.lunch_15_20_days_val, full.lunch_15_20_days, full.pse_eligible, 'beneficiaries');
                        case "lunch2124": return renderPercentageAndPartials(full.lunch_21_24_days_val, full.lunch_21_24_days, full.pse_eligible, 'beneficiaries');
                        case "lunch25": return renderPercentageAndPartials(full.lunch_25_days_val, full.lunch_25_days, full.pse_eligible, 'beneficiaries');
                        case "thr0": return renderPercentageAndPartials(full.thr_0_days_val, full.thr_0_days, full.thr_eligible, 'THR');
                        case "thr17": return renderPercentageAndPartials(full.thr_1_7_days_val, full.thr_1_7_days, full.thr_eligible, 'THR');
                        case "thr814": return renderPercentageAndPartials(full.thr_8_14_days_val, full.thr_8_14_days, full.thr_eligible, 'THR');
                        case "thr1520": return renderPercentageAndPartials(full.thr_15_20_days_val, full.thr_15_20_days, full.thr_eligible, 'THR');
                        case "thr2124": return renderPercentageAndPartials(full.thr_21_24_days_val, full.thr_21_24_days, full.thr_eligible, 'THR');
                        case "thr25": return renderPercentageAndPartials(full.thr_25_days_val, full.thr_25_days, full.thr_eligible, 'THR');

                    }
                    break;
            }

        };

    }

    function simpleRender(full, indicator, outputType) {
        var output;
        if (outputType === 'raw') {
            output = full[indicator] !== vm.dataNotEntered ? full[indicator] : vm.dataNotEntered;
        } else if (outputType === 'booleanRaw') {
            output = full[indicator] !== vm.dataNotEntered ? (full[indicator] ? 'Yes' : 'No') : vm.dataNotEntered;
        }
        return isMobile ? output : '<div>' + output + '</div>';
    }


    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.selectedLocations = [];
    vm.selectedLocationLevel = storageService.getKey('search')['selectedLocationLevel'] || 0;

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

    // mobile helpers
    const NO_TOOLTIP_DISPLAYED = -1;
    const DEFAULT_SORTED_COLUMN = 0;
    const SORT_ASCENDING = 0;
    const DEFAULT_REQUEST_DATA_STARTING_FROM = 0;
    vm.showSortPopup = false;
    vm.hasHeaderTooltips = true;
    vm.isTabularDataDisplayed = true;
    vm.tooltipDisplayed = NO_TOOLTIP_DISPLAYED; // '-1' when none of the tooltips are displayed in sort popup
    vm.requestDataStartingFrom = DEFAULT_REQUEST_DATA_STARTING_FROM; // could be any multiple of 10
    vm.dataSortingDirection = SORT_ASCENDING;
    vm.sortingColumn = DEFAULT_SORTED_COLUMN;
    vm.sortableInputKpiData = [];
    vm.showSortingInfo = function (tooltipNumber) {
        // when clicked on 'i' icon, get the column number on which info is requested and show only corresponding info.
        vm.tooltipDisplayed = tooltipNumber;
    };
    vm.toggleSortPopup = function (event) {
        vm.tooltipDisplayed = NO_TOOLTIP_DISPLAYED;
        vm.showSortPopup = !vm.showSortPopup;
        // At the top level element, click event is added, which when triggered closes sort popup
        // this is triggered when there is click action anywhere on the page.
        // But we dont need the click event which triggers the popup opening, to bubble up to the top, which will close it.
        // hence preventing any click event on the pop up and sort button.
        event.stopPropagation();
    };
    vm.clearSorting = function (event) {
        // resets to sorting by location name and closes sort popup
        vm.dataSortingDirection = SORT_ASCENDING;
        vm.sortingColumn = DEFAULT_SORTED_COLUMN;
        vm.sortableInputKpiData = [];
        vm.requestDataStartingFrom = DEFAULT_REQUEST_DATA_STARTING_FROM;
        vm.getData();
        vm.toggleSortPopup(event);
    };
    vm.getMobileData = function (index) {
        // triggers when clicked on any of the headings in sort popup
        if (vm.sortingColumn === index + 1) {
            vm.dataSortingDirection = 1 - vm.dataSortingDirection;
        } else {
            vm.dataSortingDirection = SORT_ASCENDING;
        }
        vm.sortingColumn = index + 1;
        vm.sortableInputKpiData = [];
        vm.requestDataStartingFrom = DEFAULT_REQUEST_DATA_STARTING_FROM;
        vm.getData();
    };
    vm.getMobileCustomParams = function () {
        // usually data aggregation level is set after getting network response. This is used to make initial request
        switch (vm.selectedLocationLevel) {
            case '-1' :
                vm.dataAggregationLevel = 1;
                break;
            case '0' :
                vm.dataAggregationLevel = 2;
                break;
            case '1' :
                vm.dataAggregationLevel = 3;
                break;
            case '2' :
                vm.dataAggregationLevel = 4;
                break;
            case '3' :
                vm.dataAggregationLevel = 5;
                break;
            default :
                vm.dataAggregationLevel = 1;
        }
        // This fn. spoofs the ajax request made by datatable on web for mobile requests.
        // Datatable adds these params to the network request:
        // field names of all the columns as "columns[i][data]" (Achieving this on mobile by traversing sddTableData),
        // column which is being sorted as 'order[0][column]' (getting this based on the option clicked in sort popup)
        // sorting direction as 'order[0][dir]' (when clicked on same column twice, switching direction, else default)
        var mobileCustomParams = {
            'columns[0][data]' : vm.getLocationLevelNameAndField()['locationLevelNameField'],
            'order[0][column]' : vm.sortingColumn,
            'order[0][dir]' : vm.dataSortingDirection ? 'desc' : 'asc',
            'start' : vm.requestDataStartingFrom,
            'length' : 10
        };
        var tableData = vm.getTableData();
        for(var i = 1; i <= tableData.length; i++) {
            mobileCustomParams['columns[' + i + '][data]'] = tableData[i - 1]['mData'];
        }
        return mobileCustomParams;
    };

    // this function generates data from network response & sddTableData to provide input to sortable kpis.
    vm.generateSortableKpiData = function () {
        var locationLevelNameField = vm.getLocationLevelNameAndField()['locationLevelNameField'];
        var tableData = vm.getTableData();
        var existingDataLength = vm.sortableInputKpiData.length;
        for (var i = existingDataLength; i < (vm.data.length + existingDataLength); i++) {
            vm.sortableInputKpiData[i] = {};
            vm.sortableInputKpiData[i]['cardHeading'] = vm.data[i - existingDataLength][locationLevelNameField];
            vm.sortableInputKpiData[i]['attributes'] = [];
            for (var j = 0; j < tableData.length; j++) {
                var kpiObject = {
                    'heading' : tableData[j]['heading'],
                    'value' : renderCellValue(tableData[j]['columnValueType'],tableData[j]['columnValueIndicator'])('', '', vm.data[i - existingDataLength]),
                    'isTheSortedColumn' : j === (vm.sortingColumn - 1),
                    'sortingDirection' : vm.dataSortingDirection
                };
                // adding the sorted column as first element (unshift adds elements to array at beginning, push at end)
                if (kpiObject['isTheSortedColumn']) {
                    vm.sortableInputKpiData[i]['attributes'].unshift(kpiObject);
                } else {
                    vm.sortableInputKpiData[i]['attributes'].push(kpiObject);
                }
            }
        }
    };
    // end mobile helpers

    vm.getData = function () {
        // If $location.search() is directly assigned to requestParams variable, It is assigned along with reference.
        // So, any change made to requestParams will be reflected in $location also (affecting the url). To avoid this,
        // we are deep cloning the object ($location.search()) before assigning it to request params
        var requestParams = JSON.parse(JSON.stringify($location.search()));
        if (isMobile) {
            var mobileCustomParams = vm.getMobileCustomParams();
            for(var k in mobileCustomParams) {
                requestParams[k] = mobileCustomParams[k];
            }
        }
        var getUrl = url(vm.isDetailsDisplayed ? 'service_delivery_dashboard_details' : 'service_delivery_dashboard', vm.step);
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: requestParams,
        }).then(
            function (response) {
                vm.data = response.data.data;
                var dataAvailable = vm.data && vm.data.length !== 0;
                var isAwcsLaunched = dataAvailable && !isZeroNullUnassignedOrDataNotEntered(vm.data[0]['num_launched_awcs']);
                var beneficiariesExpected = dataAvailable && !isZeroNullUnassignedOrDataNotEntered(vm.data[0]['pse_eligible']);

                vm.isCbeSeeMoreDisplayed = isAwcsLaunched;
                vm.isTHRSeeMoreDisplayed = isAwcsLaunched && (vm.step === 'pw_lw_children') &&
                    !isZeroNullUnassignedOrDataNotEntered(vm.data[0]['thr_eligible']);
                vm.isSNSeeMoreDisplayed = isAwcsLaunched && (vm.step === 'children') &&
                    beneficiariesExpected;
                vm.isPSESeeMoreDisplayed = isAwcsLaunched && (vm.step === 'children') &&
                    beneficiariesExpected;

                vm.dataAggregationLevel = response.data.aggregationLevel;
                vm.totalNumberOfEntries = response.data.recordsTotal;
                vm.setDtColumns();
                if (isMobile) {
                    vm.generateSortableKpiData();
                }
            },
            function (error) {
                $log.error(error);
            }
        );
    };

    $scope.$on('filtersChange', function () {
        vm.getData();
    });

    vm.getData();

    jQuery(function($) {
        $('#summaryList').bind('scroll', function () {
            // this function runs when end of summary list is reached and if totalRecords are not yet requested
            // Also requests are prevented for initial requests
            // Reference: http://jsfiddle.net/doktormolle/w7X9N/
            if (($(this).scrollTop() + $(this).innerHeight() >= $(this)[0].scrollHeight) &&
                ((vm.requestDataStartingFrom + 10) < vm.totalNumberOfEntries) && vm.sortableInputKpiData.length) {
                vm.requestDataStartingFrom += 10;
                vm.getData();
            }
        })
    });
}

ServiceDeliveryDashboardController.$inject = ['$rootScope', '$scope', '$http', '$location', '$routeParams', '$log',
    'DTOptionsBuilder', 'DTColumnBuilder', '$compile', 'storageService', 'userLocationId', 'baseControllersService',
    'haveAccessToAllLocations', 'isAlertActive', 'sddMetadata', 'dateHelperService', 'navigationService', 'isMobile',
    'haveAccessToFeatures',];

window.angular.module('icdsApp').directive('serviceDeliveryDashboard', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: function () {
            return templateProviderService.getTemplate('service-delivery-dashboard');
        },
        bindToController: true,
        controller: ServiceDeliveryDashboardController,
        controllerAs: '$ctrl',
    };
}]);
