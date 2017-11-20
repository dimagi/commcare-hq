/* global moment */

function PrevisionVsAchievementsGraphController($scope, reportsDataService, filtersService) {
    var vm = this;
    vm.title = "Prevision vs Achievements";
    var currentYear = new Date().getFullYear();

    var defaultStartDate = moment(new Date(currentYear, 0, 1)).format('YYYY-MM-DD');
    var defaultEndDate = moment().format('YYYY-MM-DD');
    var defaultDate = {startDate: defaultStartDate, endDate: defaultEndDate};
    vm.kp_prev_visit_date = defaultDate;
    vm.htc_tst_post_date = defaultDate;
    vm.htc_pos_post_date = defaultDate;
    vm.htc_tst_hiv_test_date = defaultDate;
    vm.htc_pos_hiv_test_date = defaultDate;
    vm.care_new_date_handshake = defaultDate;
    vm.tx_new_first_art_date = defaultDate;
    vm.tx_undetect_date_last_vl_test = defaultDate;

    vm.pickerOptions = {
        opens: "left",
        drops: "up",
        showDropdowns: true,
        locale: {
            format: "YYYY-MM-DD",
        },
    };

    vm.filters = {
        target_fiscal_year: new Date().getFullYear(),
        kp_prev_visit_date_start: vm.kp_prev_visit_date.startDate,
        kp_prev_visit_date_end: vm.kp_prev_visit_date.endDate,
        htc_tst_post_date_start: vm.htc_tst_post_date.startDate,
        htc_tst_post_date_end: vm.htc_tst_post_date.endDate,
        htc_pos_post_date_start: vm.htc_pos_post_date.startDate,
        htc_pos_post_date_end: vm.htc_pos_post_date.endDate,
        htc_tst_hiv_test_date_start: vm.htc_tst_hiv_test_date.startDate,
        htc_tst_hiv_test_date_end: vm.htc_tst_hiv_test_date.endDate,
        htc_pos_hiv_test_date_start: vm.htc_pos_hiv_test_date.startDate,
        htc_pos_hiv_test_date_end: vm.htc_pos_hiv_test_date.endDate,
        care_new_date_handshake_start: vm.care_new_date_handshake.startDate,
        care_new_date_handshake_end: vm.care_new_date_handshake.endDate,
        tx_new_first_art_date_start: vm.tx_new_first_art_date.startDate,
        tx_new_first_art_date_end: vm.tx_new_first_art_date.endDate,
        tx_undetect_date_last_vl_test_start: vm.tx_undetect_date_last_vl_test.startDate,
        tx_undetect_fdate_last_vl_test_end: vm.tx_undetect_date_last_vl_test.endDate,
    };

    vm.districts = [];
    vm.visitsTypes = [];
    vm.activityTypes = [];
    vm.clientTypes = [];
    vm.cbos = [];
    vm.fiscalYears = [];
    vm.userpls = [];
    vm.groups = [];

    vm.hivStatuses = [
        {id: '', value: 'All'},
        {id: 'unknown', value: 'Unknown'},
        {id: 'negative', value: 'Negative'},
        {id: 'positive', value: 'Positive'},
        {id: 'unclear', value: 'Unclear'},
    ];

    vm.activityTypes = [
        {id: '', value: 'All'},
        {id: 'epm', value: 'EPM'},
        {id: 'mat_distribution', value: 'Material Distribution'},
    ];

    vm.visitsTypes = [
        {id: '', value: 'All'},
        {id: 'first_visit', value: 'First Visit'},
        {id: 'follow_up_visit', value: 'Follow Up Visit'},
    ];

    vm.clientTypes = [
        {id: '', value: 'All'},
        {id: 'FSW', value: 'FSW'},
        {id: 'MSM', value: 'MSM'},
        {id: 'client_fsw', value: 'Client FSW'},
    ];

    vm.undetectvl = [
        {id: '', value: 'All'},
        {id: 'yes', value: 'Yes'},
        {id: 'no', value: 'No'},
    ];


    vm.ageRanges = [
        {id: '', value: 'All'},
        {id: '10-14 yrs', value: '10-14 yrs'},
        {id: '15-19 yrs', value: '15-19 yrs'},
        {id: '20-24 yrs', value: '20-24 yrs'},
        {id: '25-50 yrs', value: '25-50 yrs'},
        {id: '50+ yrs', value: '50+ yrs'},
    ];

    vm.ages = [];
    for (var age=0; age <= 100; age++) {
        vm.ages.push({
            value: age,
            id: age,
        });
    }

    for (var year=2014; year <= (currentYear + 4); year++ ) {
        vm.fiscalYears.push({
            value: year,
            id: year,
        });
    }

    $scope.$watch(function () {
        return vm.kp_prev_visit_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.kp_prev_visit_date_start = vm.kp_prev_visit_date.startDate.format('YYYY-MM-DD');
        vm.filters.kp_prev_visit_date_end = vm.kp_prev_visit_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.htc_tst_post_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.htc_tst_post_date_start = vm.htc_tst_post_date.startDate.format('YYYY-MM-DD');
        vm.filters.htc_tst_post_date_end = vm.htc_tst_post_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.htc_pos_post_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.htc_pos_post_date_start = vm.htc_pos_post_date.startDate.format('YYYY-MM-DD');
        vm.filters.htc_pos_post_date_end = vm.htc_pos_post_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.htc_tst_hiv_test_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.htc_tst_hiv_test_date_start = vm.htc_tst_hiv_test_date.startDate.format('YYYY-MM-DD');
        vm.filters.htc_tst_hiv_test_date_end = vm.htc_tst_hiv_test_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.htc_pos_hiv_test_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.htc_pos_hiv_test_date_start = vm.htc_pos_hiv_test_date.startDate.format('YYYY-MM-DD');
        vm.filters.htc_pos_hiv_test_date_end = vm.htc_pos_hiv_test_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.care_new_date_handshake;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.care_new_date_handshake_start = vm.care_new_date_handshake.startDate.format('YYYY-MM-DD');
        vm.filters.care_new_date_handshake_end = vm.care_new_date_handshake.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.tx_new_first_art_date;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.tx_new_first_art_date_start = vm.tx_new_first_art_date.startDate.format('YYYY-MM-DD');
        vm.filters.tx_new_first_art_date_end = vm.tx_new_first_art_date.endDate.format('YYYY-MM-DD');
    }, true);

    $scope.$watch(function () {
        return vm.tx_undetect_date_last_vl_test;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        vm.filters.tx_undetect_date_last_vl_test_start = vm.tx_undetect_date_last_vl_test.startDate.format('YYYY-MM-DD');
        vm.filters.tx_undetect_date_last_vl_test_end = vm.tx_undetect_date_last_vl_test.endDate.format('YYYY-MM-DD');
    }, true);

    vm.getData = function() {
        reportsDataService.getPrevisionVsAchievementsData(vm.filters).then(function (response) {
            vm.chartData = response.data.chart;
            filtersService.districtFilter().then(function (response) {
                vm.districts = response.data.options;
            });
            filtersService.targetCBOFilter().then(function (response) {
                vm.cbos = response.data.options;
            });
            filtersService.targetUserplFilter().then(function (response) {
                vm.userpls = response.data.options;
            });
            filtersService.groupsFilter().then(function (response) {
                vm.groups = response.data.options;
            });
        });
    };
    vm.getData();

    vm.chartOptions = {
        "chart": {
            "type": "multiBarChart",
            "height": 450,
            "margin": {
                "top": 20,
                "right": 20,
                "bottom": 60,
                "left": 50,
            },
            "clipEdge": true,
            "staggerLabels": false,
            "transitionDuration": 500,
            "stacked": false,
            "showControls": false,
            "xAxis": {
                "axisLabel": "",
                "showMaxMin": false,
            },
            "yAxis": {
                "axisLabel": "",
                "axisLabelDistance": 40,
            },
        },
    };
}

PrevisionVsAchievementsGraphController.$inject = ['$scope', 'reportsDataService', 'filtersService'];