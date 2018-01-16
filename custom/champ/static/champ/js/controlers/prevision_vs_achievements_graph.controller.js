/* global moment */
var ALL_OPTION = {id: '', value: 'All'};

function PrevisionVsAchievementsGraphController($scope, reportsDataService, filtersService) {
    var vm = this;
    vm.title = "Prevision vs Achievements";
    var currentYear = new Date().getFullYear();

    var defaultStartDate = moment(new Date(currentYear, 0, 1)).format('YYYY-MM-DD');
    var defaultEndDate = moment().format('YYYY-MM-DD');
    var defaultDate = {startDate: defaultStartDate, endDate: defaultEndDate};


    vm.kp_prev_age = ALL_OPTION;
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
        tx_undetect_date_last_vl_test_end: vm.tx_undetect_date_last_vl_test.endDate,
        target_district: [],
        target_cbo: [],
        target_userpl: [],
        target_clienttype: [],
    };

    vm.districts = [];
    vm.districtsTmp = [];
    vm.visitsTypes = [];
    vm.activityTypes = [];
    vm.clientTypes = [];
    vm.clienttypes = [];
    vm.cbos = [];
    vm.cbosTmp = [];
    vm.fiscalYears = [];
    vm.userpls = [];
    vm.userplsTmp = [];
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

    vm.want_hiv_test = [
        {id: '', value: 'All'},
        {id: 'yes', value: 'Yes'},
        {id: 'no', value: 'No'},
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

    $scope.$watch(function () {
        return vm.kp_prev_age;
    }, function (newValue, oldValue) {
        if (newValue === oldValue) {
            return;
        }
        if (vm.kp_prev_age.id !== '' && vm.kp_prev_age.id !== '50+ yrs') {
            var ranges = vm.kp_prev_age.id.split(" ")[0].split("-");
            vm.filters.kp_prev_age_start = ranges[0];
            vm.filters.kp_prev_age_end = ranges[1];
        } else if (vm.kp_prev_age.id === '50+ yrs') {
            vm.filters.kp_prev_age_start = 50;
            vm.filters.kp_prev_age_end = 200;
        } else {
            vm.filters.kp_prev_age_start = '';
            vm.filters.kp_prev_age_end = '';
        }

    }, true);

    vm.getData = function() {
        reportsDataService.getPrevisionVsAchievementsData(vm.filters).then(function (response) {
            vm.chartData = response.data.chart;
            filtersService.groupsFilter().then(function (response) {
                vm.groups = response.data.options;
            });
            filtersService.hierarchy().then(function (response) {
                vm.districtsTmp = response.data.districts;
                vm.cbosTmp = response.data.cbos;
                vm.clienttypes = response.data.clienttypes;
                vm.userplsTmp = response.data.userpls;

                vm.districts = vm.districtsTmp.slice();
                vm.cbos = vm.cbosTmp.slice();
                vm.userpls = vm.userplsTmp.slice();
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
                "left": 100,
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

    vm.districtOnSelect = function ($item) {
        vm.filters.target_cbo = [];
        vm.filters.target_userpl = [];
        vm.filters.target_clienttype = [];

        if ($item.id === '') {
            vm.filters.target_district = [$item.id];
        } else if (vm.filters.target_district.indexOf('') !== -1) {
            vm.filters.target_district = [$item.id];
        }

        var ids = vm.filters.target_district;

        if (ids.length === 0 || $item.id === '') {
            vm.cbos = vm.cbosTmp.slice();
            vm.userpls = vm.userplsTmp.slice();
        } else {
            vm.cbos = [ALL_OPTION].concat(vm.cbosTmp.slice().filter(function (item) {
                return ids.indexOf(item.parent_id) !== -1;
            }));
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var cbos = vm.cbosTmp.slice().filter(function (cbo) {
                        return ids.indexOf(cbo.parent_id) !== -1;
                    }).map(function (cbo) { return cbo.id; });
                    return cbos.indexOf(clienttype.parent_id) !== -1;
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));

        }

    };

    vm.cboOnSelect = function ($item) {
        vm.filters.target_userpl = [];
        vm.filters.target_clienttype = [];

        if ($item.id === '') {
            vm.filters.target_cbo = [$item.id];
        } else if (vm.filters.target_cbo.indexOf('') !== -1) {
            vm.filters.target_cbo = [$item.id];
        }

        var ids = vm.filters.target_cbo;

        var selectedDistrict = vm.filters.target_district;
        if ((ids.indexOf('') !== -1 || ids.length === 0) && (selectedDistrict.indexOf('') !== -1 || selectedDistrict.length === 0)) {
            vm.userpls = vm.userplsTmp.slice();
        } else if ((ids.indexOf('') !== -1 || ids.length === 0) && selectedDistrict.indexOf('') === -1) {
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var cbos = vm.cbosTmp.slice().filter(function (cbo) {
                        return selectedDistrict.indexOf(cbo.parent_id) !== -1;
                    }).map(function (cbo) { return cbo.id; });
                    return cbos.indexOf(clienttype.parent_id) !== -1;
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));
        } else {
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    return ids.indexOf(clienttype.parent_id) !== -1;
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            });
        }
    };

    vm.clienttypeOnSelect = function ($item) {
        vm.filters.target_userpl = [];

        if ($item.id === '') {
            vm.filters.target_clienttype = [$item.id];
        } else if (vm.filters.target_clienttype.indexOf('') !== -1) {
            vm.filters.target_clienttype = [$item.id];
        }

        var ids = vm.filters.target_clienttype.map(function(type) {
            if (type === 'client_fsw') {
                return 'cfsw';
            }
            return type.toLowerCase();
        });

        var selectedCbo = vm.filters.target_cbo;
        var selectedDistrict = vm.filters.target_district;
        if (selectedCbo.indexOf('') === -1 && selectedCbo.length > 0) {
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var type = clienttype.id.split("_")[0];
                    return selectedCbo.indexOf(clienttype.parent_id) !== -1 && (ids.indexOf(type) !== -1 || ids.indexOf('') !== -1 || ids.length === 0);
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));
        } else if (selectedDistrict.indexOf('') === -1 && selectedDistrict.length > 0) {
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var cbos = vm.cbosTmp.slice().filter(function (cbo) {
                        return selectedDistrict.indexOf(cbo.parent_id) !== -1;
                    }).map(function (cbo) { return cbo.id; });
                    var type = clienttype.id.split("_")[0];
                    return cbos.indexOf(clienttype.parent_id) !== -1 && (ids.indexOf(type) !== -1 || ids.indexOf('') !== -1 || ids.length === 0);
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));
        } else {
            vm.userpls = [ALL_OPTION].concat(vm.userplsTmp.slice().filter(function(item) {
                var clienttypes = vm.clienttypes.slice().filter(function(clienttype) {
                    var type = clienttype.id.split("_")[0];
                    return ids.indexOf(type) !== -1;
                }).map(function (ct) { return ct.id; });
                return clienttypes.indexOf(item.parent_id) !== -1;
            }));
        }
    };

    vm.onSelectOption = function($item, property) {
        if ($item.id === '') {
            vm.filters[property] = [$item.id];
        } else if (vm.filters[property].indexOf('') !== -1) {
            vm.filters[property] = [$item.id];
        }
    };
}

PrevisionVsAchievementsGraphController.$inject = ['$scope', 'reportsDataService', 'filtersService'];