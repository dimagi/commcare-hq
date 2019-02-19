/* global ko, $, hqImport, moment, nv, d3 */
hqDefine("champ/js/knockout/service_uptake", function() {

    var url = hqImport('hqwebapp/js/initial_page_data').reverse;

    function serviceUptakeModel() {
        var self = {};

        self.months = [];
        self.years = [];
        self.chart = void(0);

        self.title = "Prevision vs Achievements";
        self.availableDistricts = ko.observableArray();
        self.fiscalYears = ko.observableArray();
        self.groups = ko.observableArray();
        self.filters = {
            district: ko.observableArray(),
            visit_type: ko.observable(),
            activity_type: ko.observable(),
            client_type: ko.observableArray(),
            organization: ko.observableArray(),
            month_start: ko.observable(1),
            month_end: ko.observable(new Date().getMonth() + 1),
            year_start: ko.observable(new Date().getFullYear()),
            year_end: ko.observable(new Date().getFullYear()),

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

        self.chart = void(0);

        moment.months().forEach(function(key, value) {
            self.months.push({
                text: key,
                id: value + 1,
            });
        });

        for (var year=2014; year <= new Date().getFullYear(); year++ ) {
            self.years.push({
                text: year,
                id: year,
            });
        }

        self.getData = function() {
            var hierarchy_url = url('hierarchy');
            $.getJSON(hierarchy_url, function(data) {
                self.districts = data.districts;
                self.availableDistricts(self.districts);
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

        self.getChartData = function () {
            var get_url = url('service_uptake');
            $.post(get_url, ko.toJSON(self.filters), function(data) {
                self.chart.xAxis.tickValues(data.tickValues);
                d3.select('#chart').datum(data.chart).call(self.chart);
                nv.utils.windowResize(self.chart.update);
                $('#report-loading-container').hide();
            });
        };

        self.submit = function () {
            $('#report-loading-container').show();
            self.getChartData();
        };

        nv.addGraph(function () {
            self.chart = nv.models.lineChart().useInteractiveGuideline(true);

            self.chart.xAxis.axisLabel('').showMaxMin(true);
            self.chart.xAxis.tickFormat(function(d) {
                return d3.time.format('%b %Y')(new Date(d));
            });
            self.chart.yAxis.axisLabel('');
            self.chart.yAxis.tickFormat(function(d){
                return d3.format(".2%")(d);
            });
            self.chart.margin(20, 20, 60, 100);
            self.getChartData(self.chart);
            nv.utils.windowResize(self.chart.update);
            return self.chart;
        });

        self.getChartData();

        return self;
    }

    return {
        model: serviceUptakeModel,
    };
});
