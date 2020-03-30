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
    vm.haveAccessToAllLocations = haveAccessToAllLocations;
    vm.tooltipPlacement = "right";
    vm.filters = ['gender', 'age'];
    vm.userLocationId = userLocationId;
    vm.dataNotEntered = "Data Not Entered";
    vm.showTable = true;
    vm.dataAggregationLevel = 1;
    vm.isAlertActive = isAlertActive;

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
            },
            {
                'mData': 'pse',
                'heading': 'Pre-school Education (21+ days)',
                'tooltipValue': 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 21 days in the current month.',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'pse',
            },
            {
                'mData': 'gm',
                'heading': 'Growth Monitoring',
                'tooltipValue': 'Of the total children between <b>3-5 years</b> of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.<br><br><b>Growth Monitoring is done only for children till 5 years of age.</b>',
                'columnValueType': 'percentage',
                'columnValueIndicator': 'gm36',
            },
        ],
    };

    vm.getTableData = function () {
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
        return (parseInt(vm.selectedLocationLevel, 10) === 3);
    };

    vm.buildDataTable = function () {
        var tableData = vm.getTableData();
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
        var getUrl = url('service_delivery_dashboard', vm.step);
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: requestParams,
        }).then(
            function (response) {
                vm.data = response.data.data;
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
