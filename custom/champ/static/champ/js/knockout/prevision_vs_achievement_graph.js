/* global ko, $, hqImport, moment, nv, d3 */
hqDefine("champ/js/knockout/prevision_vs_achievement_graph", function() {

    var ALL_OPTION = {'id': '', 'text': 'All'};
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;

    function precisionVsAchievementsGraphModel() {
        var self = {};
        var currentYear = new Date().getFullYear();

        var defaultStartDate = moment(new Date(currentYear, 0, 1)).format('YYYY-MM-DD');
        var defaultEndDate = moment().format('YYYY-MM-DD');
        var defaultDate = defaultStartDate + ' - ' + defaultEndDate;

        self.title = "Prevision vs Achievements";
        self.availableDistricts = ko.observableArray();
        self.availableCbos = ko.observableArray();
        self.availableUserpls = ko.observableArray();
        self.fiscalYears = ko.observableArray();
        self.groups = ko.observableArray();
        self.districts = [];
        self.cbos = [];
        self.userpls = [];
        self.clienttypes = [];
        self.filters = {
            target_fiscal_year: ko.observable(currentYear),
            target_district: ko.observableArray(),
            target_cbo: ko.observableArray(),
            target_userpl: ko.observableArray(),
            target_clienttype: ko.observableArray(),
            kp_prev_age: ko.observableArray(),
            kp_prev_district: ko.observableArray(),
            kp_prev_visit_type: ko.observable(),
            kp_prev_activity_type: ko.observable(),
            kp_prev_client_type: ko.observableArray(),
            kp_prev_visit_date: ko.observable(defaultDate),
            kp_prev_user_group: ko.observableArray(),
            htc_tst_post_date: ko.observable(defaultDate),
            htc_tst_hiv_test_date: ko.observable(defaultDate),
            htc_tst_age_range: ko.observableArray(),
            htc_tst_district: ko.observableArray(),
            htc_tst_client_type: ko.observableArray(),
            htc_tst_user_group: ko.observableArray(),
            htc_pos_age_range: ko.observableArray(),
            htc_pos_district: ko.observableArray(),
            htc_pos_client_type: ko.observableArray(),
            htc_pos_post_date: ko.observable(defaultDate),
            htc_pos_hiv_test_date: ko.observable(defaultDate),
            htc_pos_user_group: ko.observableArray(),
            care_new_age_range: ko.observableArray(),
            care_new_district: ko.observableArray(),
            care_new_client_type: ko.observableArray(),
            care_new_hiv_status: ko.observableArray(),
            care_new_date_handshake: ko.observable(defaultDate),
            care_new_user_group: ko.observableArray(),
            tx_new_age_range: ko.observableArray(),
            tx_new_district: ko.observableArray(),
            tx_new_client_type: ko.observableArray(),
            tx_new_first_art_date: ko.observable(defaultDate),
            tx_new_hiv_status: ko.observableArray(),
            tx_new_user_group: ko.observableArray(),
            tx_undetect_age_range: ko.observableArray(),
            tx_undetect_district: ko.observableArray(),
            tx_undetect_client_type: ko.observableArray(),
            tx_undetect_vl: ko.observable(),
            tx_undetect_hiv_status: ko.observableArray(),
            tx_undetect_date_last_vl_test: ko.observable(defaultDate),
            tx_undetect_user_group: ko.observableArray(),
        };

        self.availableClientTypes = [
            {id: '', text: 'All'},
            {id: 'FSW', text: 'FSW'},
            {id: 'MSM', text: 'MSM'},
            {id: 'client_fsw', text: 'Client FSW'},
        ];

        self.undetectedVL = [
            {id: '', text: 'All'},
            {id: 'yes', text: 'Yes'},
            {id: 'no', text: 'No'},
        ];

        self.ageRanges = [
            {id: '', text: 'All'},
            {id: '10-14 yrs', text: '10-14 yrs'},
            {id: '15-19 yrs', text: '15-19 yrs'},
            {id: '20-24 yrs', text: '20-24 yrs'},
            {id: '25-50 yrs', text: '25-50 yrs'},
            {id: '50+ yrs', text: '50+ yrs'},
        ];

        self.visitsTypes = [
            {id: '', text: 'All'},
            {id: 'first_visit', text: 'First Visit'},
            {id: 'follow_up_visit', text: 'Follow Up Visit'},
        ];

        self.activityTypes = [
            {id: '', text: 'All'},
            {id: 'epm', text: 'EPM'},
            {id: 'mat_distribution', text: 'Material Distribution'},
        ];

        self.wantHivTest = [
            {id: '', text: 'All'},
            {id: 'yes', text: 'Yes'},
            {id: 'no', text: 'No'},
        ];

        self.hivStatuses = [
            {id: '', text: 'All'},
            {id: 'unknown', text: 'Unknown'},
            {id: 'negative', text: 'Negative'},
            {id: 'positive', text: 'Positive'},
            {id: 'unclear', text: 'Unclear'},
        ];

        self.chart = void(0);

        for (var year=2014; year <= (currentYear + 4); year++ ) {
            self.fiscalYears().push({
                text: year,
                id: year,
            });
        }

        self.getData = function() {
            var hierarchy_url = url('hierarchy');
            $.getJSON(hierarchy_url, function(data) {
                self.districts = data.districts;
                self.cbos = data.cbos;
                self.userpls = data.userpls;
                self.clienttypes = data.clienttypes;
                self.availableDistricts(self.districts);
                self.availableCbos(self.cbos);
                self.availableUserpls(self.userpls);
            });
            var group_url = url('group_filter');
            $.getJSON(group_url, function(data) {
                self.groups(data.options);
            });
        };

        self.getData();

        self.districtOnSelect = function (event) {
            if (event.added !== void(0)) {
                var $item = event.added;

                self.filters.target_cbo([]);
                self.filters.target_userpl([]);
                self.filters.target_clienttype([]);

                if ($item.id === '' || self.filters.target_district().indexOf('') !== -1) {
                    self.filters.target_district([$item.id]);
                }
                var ids = self.filters.target_district();

                if (ids.length === 0 || $item.id === '') {
                    self.availableCbos(self.cbos.slice());
                    self.availableUserpls(self.availableUserpls.slice());
                } else {
                    self.availableCbos([ALL_OPTION].concat(self.cbos.slice().filter(function (item) {
                        return ids.indexOf(item.parent_id) !== -1;
                    })));
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function(item) {
                        var clienttypes = self.clienttypes.slice().filter(function(clienttype) {
                            var cbos = self.cbos.slice().filter(function (cbo) {
                                return ids.indexOf(cbo.parent_id) !== -1;
                            }).map(function (cbo) { return cbo.id; });
                            return cbos.indexOf(clienttype.parent_id) !== -1;
                        }).map(function (ct) { return ct.id; });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                }
            }
        };

        self.cboOnSelect = function (event) {
            if (event.added !== void(0)) {
                var $item = event.added;
                self.filters.target_userpl([]);
                self.filters.target_clienttype([]);

                if ($item.id === '' || self.filters.target_cbo().indexOf('') !== -1) {
                    self.filters.target_cbo([$item.id]);
                }

                var ids = self.filters.target_cbo();

                var selectedDistrict = self.filters.target_district();
                if ((ids.indexOf('') !== -1 || ids.length === 0) && (selectedDistrict.indexOf('') !== -1 || selectedDistrict.length === 0)) {
                    self.availableUserpls(self.userpls.slice());
                } else if ((ids.indexOf('') !== -1 || ids.length === 0) && selectedDistrict.indexOf('') === -1) {
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function (item) {
                        var clienttypes = self.clienttypes.slice().filter(function (clienttype) {
                            var cbos = self.cbos.slice().filter(function (cbo) {
                                return selectedDistrict.indexOf(cbo.parent_id) !== -1;
                            }).map(function (cbo) {
                                return cbo.id;
                            });
                            return cbos.indexOf(clienttype.parent_id) !== -1;
                        }).map(function (ct) {
                            return ct.id;
                        });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                } else {
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function (item) {
                        var clienttypes = self.clienttypes.slice().filter(function (clienttype) {
                            return ids.indexOf(clienttype.parent_id) !== -1;
                        }).map(function (ct) {
                            return ct.id;
                        });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                }
            }
        };

        self.clienttypeOnSelect = function (event) {
            if (event.added !== void(0)) {
                var $item = event.added;
                self.filters.target_userpl([]);

                if ($item.id === '') {
                    self.filters.target_clienttype([$item.id]);
                } else if (self.filters.target_clienttype.indexOf('') !== -1) {
                    self.filters.target_clienttype([$item.id]);
                }

                var ids = self.filters.target_clienttype().map(function(type) {
                    if (type === 'client_fsw') {
                        return 'cfsw';
                    }
                    return type.toLowerCase();
                });

                var selectedCbo = self.filters.target_cbo();
                var selectedDistrict = self.filters.target_district();
                if ((ids.indexOf('') !== -1 || ids.length === 0) && (selectedDistrict.indexOf('') !== -1 || selectedDistrict.length === 0) && (selectedCbo.indexOf('') !== -1 || selectedCbo.length === 0)) {
                    self.availableUserpls(self.userpls.slice());
                } else if (selectedCbo.indexOf('') === -1 && selectedCbo.length > 0) {
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function(item) {
                        var clienttypes = self.clienttypes.slice().filter(function(clienttype) {
                            var type = clienttype.id.split("_")[0];
                            return selectedCbo.indexOf(clienttype.parent_id) !== -1 && (ids.indexOf(type) !== -1 || ids.indexOf('') !== -1 || ids.length === 0);
                        }).map(function (ct) { return ct.id; });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                } else if (selectedDistrict.indexOf('') === -1 && selectedDistrict.length > 0) {
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function(item) {
                        var clienttypes = self.clienttypes.slice().filter(function(clienttype) {
                            var cbos = self.cbos.slice().filter(function (cbo) {
                                return selectedDistrict.indexOf(cbo.parent_id) !== -1;
                            }).map(function (cbo) { return cbo.id; });
                            var type = clienttype.id.split("_")[0];
                            return cbos.indexOf(clienttype.parent_id) !== -1 && (ids.indexOf(type) !== -1 || ids.indexOf('') !== -1 || ids.length === 0);
                        }).map(function (ct) { return ct.id; });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                } else {
                    self.availableUserpls([ALL_OPTION].concat(self.userpls.slice().filter(function(item) {
                        var clienttypes = self.clienttypes.slice().filter(function(clienttype) {
                            var type = clienttype.id.split("_")[0];
                            return ids.indexOf(type) !== -1;
                        }).map(function (ct) { return ct.id; });
                        return clienttypes.indexOf(item.parent_id) !== -1;
                    })));
                }
            }
        };

        self.onSelectOption = function(event, property) {
            if (event.added !== void(0)) {
                var $item = event.added;
                if ($item.id === '' || self.filters[property].indexOf('') !== -1) {
                    self.filters[property]([$item.id]);
                }
            }
        };

        self.getChartData = function (chart) {
            var get_url = url('champ_pva');
            $.post(get_url, ko.toJSON(self.filters), function(data) {
                d3.select('#chart').datum(data.chart).call(chart);
                nv.utils.windowResize(chart.update);
                $('#report-loading-container').hide();
            });
        };

        self.submit = function () {
            $('#report-loading-container').show();
            self.getChartData(self.chart);
        };

        nv.addGraph(function () {
            self.chart = nv.models.multiBarChart()
                .clipEdge(true)
                .staggerLabels(true)
                .stacked(false)
                .showControls(false);

            self.chart.xAxis.axisLabel('').showMaxMin(false);
            self.chart.yAxis.axisLabel('');
            self.chart.margin(20, 20, 60, 100);
            self.getChartData(self.chart);
            nv.utils.windowResize(self.chart.update);
            return self.chart;
        });

        var pickers = $('.date-picker');
        if (pickers.length > 0) {
            pickers.daterangepicker(
                {
                    startDate: defaultStartDate,
                    endDate: defaultEndDate,
                    locale: {
                        format: 'YYYY-MM-DD',
                    },
                }
            );
        }

        return self;
    }

    return {
        model: precisionVsAchievementsGraphModel,
    };
});
