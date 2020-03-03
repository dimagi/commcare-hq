var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ServiceDeliveryDashboardController($rootScope, $scope, $http, $location, $routeParams, $log, DTOptionsBuilder,
                                            DTColumnBuilder, $compile, storageService, userLocationId,
                                            baseControllersService, haveAccessToAllLocations, isAlertActive,
                                            sddMetadata, dateHelperService, navigationService, isMobile) {
    baseControllersService.BaseFilterController.call(
        this, $scope, $routeParams, $location, dateHelperService, storageService, navigationService
    );
    var vm = this;
    vm.data = {};
    vm.label = "Service Delivery Dashboard";
    vm.tooltipPlacement = "right";
    vm.filters = ['gender', 'age'];
    vm.userLocationId = userLocationId;
    vm.dataNotEntered = "Data Not Entered";
    vm.showTable = true;
    vm.dataAggregationLevel = 1;
    vm.isAlertActive = isAlertActive;

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

    vm.dtOptions = DTOptionsBuilder.newOptions()
        .withOption('ajax', {
            url: url('service_delivery_dashboard', vm.step),
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
        .withDOM('ltipr');

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
            'locationLevelNameField': locationLevelNameField
        }
    };

    vm.sddTableData = {
        'pw_lw_children': {
            'non-awc' : [
                {
                    'mData' : 'num_launched_awcs',
                    'heading' : 'Number of AWCs launched',
                    'tooltipValue' : 'Total Number of Anganwadi Centers launched in the selected location.',
                    'columnValueType' : 'raw',
                    'columnValueIndicator' : 'num_launched_awcs'
                },
                {
                    'mData' : 'home_visits',
                    'heading' : 'Home Visits',
                    'tooltipValue' : 'Of the total number of expected home visits, the percentage of home visits completed by AWW.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'homeVisits'
                },
                {
                    'mData' : 'gm',
                    'heading' : 'Growth Monitoring',
                    'tooltipValue' : 'Of the total children between 0-3 years of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'gm03'
                },
                {
                    'mData' : 'num_awcs_conducted_cbe',
                    'heading' : 'Community Based Events',
                    'tooltipValue' : 'Of the total number of launched Anganwadi Centers, the percentage who have conducted at least 2 Community Based Events in the given month.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'num_awcs_conducted_cbe'
                },
                {
                    'mData' : 'num_awcs_conducted_vhnd',
                    'heading' : 'VHSND',
                    'tooltipValue' : 'Total number of Anganwadi Centers who have conducted at least 1 Village, Health, Sanitation and Nutrition Day in the given month.',
                    'columnValueType' : 'raw',
                    'columnValueIndicator' : 'num_awcs_conducted_vhnd'
                },
                {
                    'mData' : 'thr',
                    'heading' : 'Take Home Ration (21+ days)',
                    'tooltipValue' : 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) and 6-36 months children who were provided THR for at least 21 days in the current month.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'thr'
                },
            ],
            'awc' : [
                {
                    'mData' : 'home_visits',
                    'heading' : 'Home Visits',
                    'tooltipValue' : 'Of the total number of expected home visits, the percentage of home visits completed by AWW.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'homeVisits'
                },
                {
                    'mData' : 'gm',
                    'heading' : 'Growth Monitoring',
                    'tooltipValue' : 'Of the total children between 0-3 years of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'gm03'
                },
                {
                    'mData' : 'num_awcs_conducted_cbe',
                    'heading' : 'Community Based Events',
                    'tooltipValue' : 'If the AWC conducted at least 2 CBE in the current month then Yes otherwise No.',
                    'columnValueType' : 'booleanRaw',
                    'columnValueIndicator' : 'num_awcs_conducted_cbe'
                },
                {
                    'mData' : 'num_awcs_conducted_vhnd',
                    'heading' : 'VHSND',
                    'tooltipValue' : 'If the AWC conducted at least 1 VHSND in the current month then Yes otherwise No.',
                    'columnValueType' : 'booleanRaw',
                    'columnValueIndicator' : 'num_awcs_conducted_vhnd'
                },
                {
                    'mData' : 'thr',
                    'heading' : 'Take Home Ration (21+ days)',
                    'tooltipValue' : 'Of the total number of pregnant women, lactating women (0-6 months children) and 6-36 months children enrolled for Anganwadi services, the percentage of pregnant women, lactating women (0-6 months children) and 6-36 months children who were provided THR for at least 21 days in the current month.',
                    'columnValueType' : 'percentage',
                    'columnValueIndicator' : 'thr'
                },
            ],
        },
        'children' : [
            {
                'mData' : 'sn',
                'heading' : 'Supplementary Nutrition (21+ days)',
                'tooltipValue' : 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal i.e. supplementary nutrition for at least 21 days in the current month.',
                'columnValueType' : 'percentage',
                'columnValueIndicator' : 'supNutrition'
            },
            {
                'mData' : 'pse',
                'heading' : 'Pre-school Education (21+ days)',
                'tooltipValue' : 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 21 days in the current month.',
                'columnValueType' : 'percentage',
                'columnValueIndicator' : 'pse'
            },
            {
                'mData' : 'gm',
                'heading' : 'Growth Monitoring',
                'tooltipValue' : 'Of the total children between <b>3-5 years</b> of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.<br><br><b>Growth Monitoring is done only for children till 5 years of age.</b>',
                'columnValueType' : 'percentage',
                'columnValueIndicator' : 'gm36'
            },
        ]
    };

    vm.getSddTableData = function () {
        var isPwLwChildren = vm.isPwLwChildrenTab();
        var isAwc = vm.isAwcDataShown();
        return isPwLwChildren ?
            (isAwc ? vm.sddTableData['pw_lw_children']['awc'] : vm.sddTableData['pw_lw_children']['non-awc']) :
            vm.sddTableData['children'];
    };

    vm.isPwLwChildrenTab = function () {
        return ($location.path().indexOf('/pw_lw_children') !== -1);
    };

    vm.isAwcDataShown = function () {
        // if sector level is selected --> selectedLocationLevel is 3
        return (parseInt($location.search()['selectedLocationLevel'], 10) === 3);
    };

    vm.buildDataTable = function () {
        var tableData = vm.getSddTableData();
        var dataTableColumns = [];
        for (var i = 0; i < tableData.length; i++) {
            dataTableColumns.push(DTColumnBuilder.newColumn(tableData[i]['mData'])
                .withTitle(renderHeaderTooltip(tableData[i]['heading'], tableData[i]['tooltipValue']))
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
            locationLevelName
        ).renderWith(renderCellValue('raw', locationLevelNameField)
        ).withClass('medium-col')];
        vm.dtColumns = vm.dtColumns.concat(vm.buildDataTable());
    };

    vm.setDtColumns();

    function compile(row) {
        $compile(window.angular.element(row).contents())($scope);
    }

    function renderHeaderTooltip(header, tooltipContent) {
        return '<i class="fa fa-info-circle headerTooltip" style="float: right;" ><div class="headerTooltipText">' + tooltipContent + '</div></i><span>' + header + '</span>';
    }

    function isZeroNullUnassignedOrDataNotEntered(value) {
        return value === 0 || value === null || value === void(0) || value === vm.dataNotEntered;
    }

    function renderPercentageAndPartials(percentage, nominator, denominator, indicator) {
        if (isZeroNullUnassignedOrDataNotEntered(denominator)) {
            return '<div> No expected ' + indicator + ' </div>';
        }
        else {
            if (denominator === vm.dataNotEntered) { return vm.dataNotEntered; }
            if (percentage === vm.dataNotEntered) {
                if (nominator === 0 && denominator === 0) {
                    return '<div><span>100 %<br>(' + nominator + ' / ' + denominator + ')</span></div>';
                }
                return '<div><span>(' + nominator + ' / ' + denominator + ')</span></div>';
            }
        }

        return '<div><span>' + percentage + '<br>(' + nominator + ' / ' + denominator + ')</span></div>';
    }


    function renderCellValue(CellType, indicator) {

        return function (data, type, full) {

            if (['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'num_launched_awcs'].indexOf(indicator) === -1 && isZeroNullUnassignedOrDataNotEntered(full['num_launched_awcs'])) {
                return '<div>Not Launched</div>';
            }

            switch (CellType) {
                case "raw": return simpleRender(full, indicator, 'raw');
                case "booleanRaw": return simpleRender(full, indicator, 'booleanRaw');
                case "percentage":
                    switch (indicator) {
                        case "homeVisits": return renderPercentageAndPartials(full.home_visits, full.valid_visits, full.expected_visits, 'Home visits');
                        case "gm03": return  renderPercentageAndPartials(full.gm, full.gm_0_3, full.children_0_3, 'Weight measurement');
                        case "gm36": return renderPercentageAndPartials(full.gm, full.gm_3_5, full.children_3_5, 'Weight measurement');
                        case "thr": return renderPercentageAndPartials(full.thr, full.thr_given_21_days, full.total_thr_candidates, 'THR');
                        case "pse": return renderPercentageAndPartials(full.pse, full.pse_attended_21_days, full.children_3_6, 'beneficiaries');
                        case "supNutrition": return renderPercentageAndPartials(full.sn, full.lunch_count_21_days, full.children_3_6, 'beneficiaries');
                        case "num_awcs_conducted_cbe": return renderPercentageAndPartials(full.cbe, full.num_awcs_conducted_cbe, full.num_launched_awcs, 'CBE');

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
        return '<div>' + output + '</div>';
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

    vm.getData = function () {
        var getUrl = url('service_delivery_dashboard', vm.step);
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data.data;
                vm.dataAggregationLevel = response.data.aggregationLevel;
                vm.setDtColumns();
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
}

ServiceDeliveryDashboardController.$inject = ['$rootScope', '$scope', '$http', '$location', '$routeParams', '$log',
    'DTOptionsBuilder', 'DTColumnBuilder', '$compile', 'storageService', 'userLocationId', 'baseControllersService',
    'haveAccessToAllLocations', 'isAlertActive', 'sddMetadata', 'dateHelperService', 'navigationService', 'isMobile'];

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
