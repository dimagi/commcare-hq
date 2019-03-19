var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ServiceDeliveryDashboardController($scope, $http, $location, $routeParams, $log, DTOptionsBuilder, DTColumnBuilder, $compile, storageService, userLocationId) {
    var vm = this;
    vm.data = {};
    vm.label = "Service Delivery Dashboard";
    vm.tooltipPlacement = "right";
    vm.filters = ['gender', 'age'];
    vm.userLocationId = userLocationId;
    vm.dataNotEntered = "Data Not Entered";
    vm.showTable = true;
    vm.dataAgeSDD = '0_3';
    vm.dataAggregationLevel = 1;

    vm.dtOptions = DTOptionsBuilder.newOptions()
        .withOption('ajax', {
            url: url('service_delivery_dashboard'),
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

    vm.setDtColumns = function () {
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
        vm.dtColumns = [DTColumnBuilder.newColumn(
            locationLevelNameField
        ).withTitle(
            locationLevelName
        ).renderWith(simpleRender(
            locationLevelNameField
        )).withClass('medium-col')];
        if (vm.dataAgeSDD === '0_3') {
            if (vm.dataAggregationLevel <= 4) {
                vm.dtColumns = vm.dtColumns.concat([
                    DTColumnBuilder.newColumn('num_launched_awcs').withTitle(renderNumLaunchedAwcsTooltip()).renderWith(simpleRender('num_launched_awcs')).withClass('medium-col'),
                    DTColumnBuilder.newColumn('home_visits').withTitle(renderHomeVisitsTooltip()).renderWith(renderHomeVisits).withClass('medium-col'),
                    DTColumnBuilder.newColumn('gm').withTitle(renderGrowthMonitoringTooltip()).renderWith(renderGrowthMonitoring03).withClass('medium-col'),
                    DTColumnBuilder.newColumn('num_awcs_conducted_cbe').withTitle(renderCommunityBasedEventsTooltip()).renderWith(simpleRender('num_awcs_conducted_cbe')).withClass('medium-col'),
                    DTColumnBuilder.newColumn('num_awcs_conducted_vhnd').withTitle(renderVHSNDTooltip()).renderWith(simpleRender('num_awcs_conducted_vhnd')).withClass('medium-col'),
                    DTColumnBuilder.newColumn('thr').withTitle(renderTakeHomeRationTooltip()).renderWith(renderTakeHomeRation).withClass('medium-col'),
                ]);
            } else {
                vm.dtColumns = vm.dtColumns.concat([
                    DTColumnBuilder.newColumn('home_visits').withTitle(renderHomeVisitsTooltip()).renderWith(renderHomeVisits).withClass('medium-col'),
                    DTColumnBuilder.newColumn('gm').withTitle(renderGrowthMonitoringTooltip()).renderWith(renderGrowthMonitoring03).withClass('medium-col'),
                    DTColumnBuilder.newColumn('num_awcs_conducted_cbe').withTitle(renderCommunityBasedEventsTooltipAWC()).renderWith(simpleYesNoRender('num_awcs_conducted_cbe')).withClass('medium-col'),
                    DTColumnBuilder.newColumn('num_awcs_conducted_vhnd').withTitle(renderVHSNDTooltipAWC()).renderWith(simpleYesNoRender('num_awcs_conducted_vhnd')).withClass('medium-col'),
                    DTColumnBuilder.newColumn('thr').withTitle(renderTakeHomeRationTooltip()).renderWith(renderTakeHomeRation).withClass('medium-col'),
                ]);
            }
        } else {
            vm.dtColumns = vm.dtColumns.concat([
                DTColumnBuilder.newColumn('sn').withTitle(renderSupplementaryNutritionTooltip()).renderWith(renderSupplementaryNutrition).withClass('medium-col'),
                DTColumnBuilder.newColumn('pse').withTitle(renderPreSchoolEducationTooltip()).renderWith(renderPreSchoolEducation).withClass('medium-col'),
                DTColumnBuilder.newColumn('gm').withTitle(renderGrowthMonitoring36Tooltip()).renderWith(renderGrowthMonitoring36).withClass('medium-col'),
            ]);
        }
    };

    vm.setDtColumns();

    function compile(row) {
        $compile(window.angular.element(row).contents())($scope);
    }

    function renderHeaderTooltip(header, tooltipContent) {
        return '<i class="fa fa-info-circle headerTooplip" style="float: right;" ><div class="headerTooplipText">' + tooltipContent + '</div></i><span>' + header + '</span>';
    }
    function renderNumLaunchedAwcsTooltip() {
        return renderHeaderTooltip('Number of AWC', 'Total Number of Anganwadi Centers launched in the selected location.');
    }
    function renderHomeVisitsTooltip() {
        return renderHeaderTooltip('Home Visits', 'Of the total number of expected home visits, the percentage of home visits completed by AWW.');
    }
    function renderGrowthMonitoringTooltip() {
        return renderHeaderTooltip('Growth Monitoring', 'Of the total children between 0-3 years of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.');
    }
    function renderCommunityBasedEventsTooltip() {
        return renderHeaderTooltip('Community Based Events', 'Total number of Anganwadi Centers who have conducted at least 1 Community Based Events in the given month.');
    }
    function renderVHSNDTooltip() {
        return renderHeaderTooltip('VHSND', 'Total number of Anganwadi Centers who have conducted at least 1 Village, Health, Sanitation and Nutrition Day in the given month.');
    }
    function renderTakeHomeRationTooltip() {
        return renderHeaderTooltip('Take Home Ration', 'Of the total number of pregnant women, lactating women and 0-3 years old children enrolled for Anganwadi services, the percentage of pregnant women, lactating women and 0-3 years old children who were provided THR for at least 21 days in the current month.');
    }
    function renderCommunityBasedEventsTooltipAWC() {
        return renderHeaderTooltip('Community Based Events', 'If the AWC conducted at least 1 CBE in the current month then Yes otherwise No.');
    }
    function renderVHSNDTooltipAWC() {
        return renderHeaderTooltip('VHSND', 'If the AWC conducted at least 1 VHSND in the current month then Yes otherwise No.');
    }
    function renderSupplementaryNutritionTooltip() {
        return renderHeaderTooltip('Supplementary Nutrition', 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who were provided Hot Cooked Meal i.e. supplementary nutrition for at least 21 days in the current month.');
    }
    function renderPreSchoolEducationTooltip() {
        return renderHeaderTooltip('Pre-school Education', 'Of the total children between 3-6 years of age and enrolled for Anganwadi services, the percentage of children who attended Pre-school education for at least 21 days in the current month.');
    }
    function renderGrowthMonitoring36Tooltip() {
        return renderHeaderTooltip('Growth Monitoring', 'Of the total children between <b>3-5 years</b> of age and enrolled for Anganwadi services, the percentage of children who were weighed in the current month.<br><br><b>Growth Monitoring is done only for children till 5 years of age.</b>');
    }

    function renderPercentageAndPartials(percentage, nominator, denominator) {
        if (denominator === vm.dataNotEntered) { return vm.dataNotEntered; }
        if (percentage === vm.dataNotEntered) {
            return '<div><span>(' + nominator + ' / ' + denominator + ')</span></div>';
        }
        return '<div><span>' + percentage + '<br>(' + nominator + ' / ' + denominator +
            ')</span></div>';
    }
    function simpleRender(indicator) {
        return function simpleRenderer(data, type, full) {
            return '<div>' + full[indicator] + '</div>' || vm.dataNotEntered;
        };
    }
    function simpleYesNoRender(indicator) {
        return function simpleRenderer(data, type, full) {
            return '<div>' + full[indicator] && full[indicator] !== vm.dataNotEntered ? 'Yes' : 'No' + '</div>' || vm.dataNotEntered;
        };
    }
    function renderHomeVisits(data, type, full) {
        return renderPercentageAndPartials(full.home_visits, full.valid_visits, full.expected_visits);
    }
    function renderGrowthMonitoring03(data, type, full) {
        return renderPercentageAndPartials(full.gm, full.gm_0_3, full.children_0_3);
    }
    function renderTakeHomeRation(data, type, full) {
        return renderPercentageAndPartials(full.thr, full.thr_given_21_days, full.total_thr_candidates);
    }
    function renderSupplementaryNutrition(data, type, full) {
        return renderPercentageAndPartials(full.sn, full.lunch_count_21_days, full.children_3_6);
    }
    function renderPreSchoolEducation(data, type, full) {
        return renderPercentageAndPartials(full.pse, full.pse_attended_21_days, full.children_3_6);
    }
    function renderGrowthMonitoring36(data, type, full) {
        return renderPercentageAndPartials(full.gm, full.gm_3_5, full.children_3_5);
    }

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.selectedLocations = [];
    vm.selectedLocationLevel = storageService.getKey('search')['selectedLocationLevel'] || 0;

    vm.getData = function () {
        var getUrl = url('service_delivery_dashboard');
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data.data;
                vm.dataAgeSDD = response.data.ageSDD;
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

ServiceDeliveryDashboardController.$inject = ['$scope', '$http', '$location', '$routeParams', '$log', 'DTOptionsBuilder', 'DTColumnBuilder', '$compile', 'storageService', 'userLocationId'];

window.angular.module('icdsApp').directive('serviceDeliveryDashboard', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'service-delivery-dashboard'),
        bindToController: true,
        controller: ServiceDeliveryDashboardController,
        controllerAs: '$ctrl',
    };
});
