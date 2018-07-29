/* global ko, $, hqImport, moment */
hqDefine("champ/js/knockout/prevision_vs_achievement_table", function() {

    var ALL_OPTION = {'id': '', 'text': 'All'};
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;

    // eslint-disable-next-line no-unused-vars
    function precisionVsAchievementsTableModel() {
        var self = {};
        var currentYear = new Date().getFullYear();

        var defaultStartDate = moment(new Date(currentYear, 0, 1)).format('YYYY-MM-DD');
        var defaultEndDate = moment().format('YYYY-MM-DD');
        var defaultDate = defaultStartDate + ' - ' + defaultEndDate;

        self.kp_prev = ko.observable();
        self.target_kp_prev = ko.observable();
        self.htc_tst = ko.observable();
        self.target_htc_tst = ko.observable();
        self.htc_pos = ko.observable();
        self.target_htc_pos = ko.observable();
        self.care_new = ko.observable();
        self.target_care_new = ko.observable();
        self.tx_new = ko.observable();
        self.target_tx_new = ko.observable();
        self.tx_undetect = ko.observable();
        self.target_tx_undetect = ko.observable();

        self.title = "Prevision vs Achievements";
        self.availableDistricts = ko.observableArray();
        self.availableCbos = ko.observableArray();
        self.fiscalYears = ko.observableArray();
        self.groups = ko.observableArray();
        self.filters = {
            district: ko.observableArray(),
            cbo: ko.observableArray(),
            visit_type: ko.observable(),
            activity_type: ko.observable(),
            client_type: ko.observableArray(),
            organization: ko.observableArray(),
            fiscal_year: ko.observable(currentYear),
            visit_date: ko.observable(defaultDate),
            post_date: ko.observable(defaultDate),
            first_art_date: ko.observable(defaultDate),
            date_handshake: ko.observable(defaultDate),
            date_last_vl_test: ko.observable(defaultDate),

        };

        self.availableClientTypes = [
            {id: '', text: 'All'},
            {id: 'FSW', text: 'FSW'},
            {id: 'MSM', text: 'MSM'},
            {id: 'client_fsw', text: 'Client FSW'},
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
                self.availableDistricts(self.districts);
                self.availableCbos(self.cbos);
            });
            var group_url = url('group_filter');
            $.getJSON(group_url, function(data) {
                self.groups(data.options);
            });
        };

        self.getData();

        self.onSelectOption = function(event, property) {
            if (event.added !== void(0)) {
                var $item = event.added;
                if ($item.id === '' || self.filters[property].indexOf('') !== -1) {
                    self.filters[property]([$item.id]);
                }
            }
        };

        self.getTableData = function () {
            var get_url = url('champ_pva_table');
            $.post(get_url, ko.toJSON(self.filters), function(data) {
                self.kp_prev(data.kp_prev);
                self.target_kp_prev(data.target_kp_prev);
                self.htc_tst(data.htc_tst);
                self.target_htc_tst(data.target_htc_tst);
                self.htc_pos(data.htc_pos);
                self.target_htc_pos(data.target_htc_pos);
                self.care_new(data.care_new);
                self.target_care_new(data.target_care_new);
                self.tx_new(data.tx_new);
                self.target_tx_new(data.target_tx_new);
                self.tx_undetect(data.tx_undetect);
                self.target_tx_undetect(data.target_tx_undetect);
                $('#report-loading-container').hide();
            });
        };

        self.submit = function () {
            $('#report-loading-container').show();
            self.getTableData();
        };

        self.submit();

        self.districtOnSelect = function (event) {
            if (event.added !== void(0)) {
                var $item = event.added;

                self.filters.cbo([]);

                if ($item.id === '' || self.filters.district().indexOf('') !== -1) {
                    self.filters.district([$item.id]);
                }
                var ids = self.filters.district();

                if (ids.length === 0 || $item.id === '') {
                    self.availableCbos(self.cbos.slice());
                } else {
                    self.availableCbos([ALL_OPTION].concat(self.cbos.slice().filter(function (item) {
                        return ids.indexOf(item.parent_id) !== -1;
                    })));
                }
            }
        };

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
        model: precisionVsAchievementsTableModel,
    };
});
