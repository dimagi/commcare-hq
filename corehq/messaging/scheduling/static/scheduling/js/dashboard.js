hqDefine("scheduling/js/dashboard",[
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'nvd3/nv.d3.min',
], function($, ko, initialPageData) {
    var dashboardUrl = initialPageData.reverse("messaging_dashboard");

    var DashboardViewModel = function() {
        var self = this;
        self.bindingApplied = ko.observable(false);
        self.last_refresh_time = ko.observable();
        self.queued_sms_count = ko.observable();
        self.uses_restricted_time_windows = ko.observable();
        self.within_allowed_sms_times = ko.observable();
        self.sms_resume_time = ko.observable();
        self.project_timezone = ko.observable();
        self.outbound_sms_sent_today = ko.observable();
        self.daily_outbound_sms_limit = ko.observable();
        self.events_pending = ko.observable();

        self.percentage_daily_outbound_sms_used = ko.computed(function() {
            return Math.round(100.0 * self.outbound_sms_sent_today() / self.daily_outbound_sms_limit());
        });

        self.is_daily_usage_ok = ko.computed(function() {
            return self.outbound_sms_sent_today() < self.daily_outbound_sms_limit();
        });

        self.is_sms_currently_allowed = ko.computed(function() {
            return self.is_daily_usage_ok() && self.within_allowed_sms_times();
        });

        self.init = function() {
            self.sms_count_chart = nv.models.multiBarChart()
                .color(['#ff7f27', '#0080c0'])
                .transitionDuration(500)
                .reduceXTicks(true)
                .rotateLabels(0)
                .showControls(false)
                .groupSpacing(0.3)
                .forceY([0, 10]);
            self.sms_count_chart.yAxis.tickFormat(d3.format(',f'));

            self.event_count_chart = nv.models.multiBarChart()
                .color(['#ed1c24', '#008000'])
                .transitionDuration(500)
                .reduceXTicks(true)
                .rotateLabels(0)
                .showControls(false)
                .groupSpacing(0.3)
                .forceY([0, 10]);
            self.event_count_chart.yAxis.tickFormat(d3.format(',f'));

            self.error_count_chart = nv.models.discreteBarChart()
                .x(function(d) { return d.label; })
                .y(function(d) { return d.value; })
                .tooltips(true)
                .showValues(true)
                .color(['#ed1c24'])
                .transitionDuration(500)
                .showXAxis(false)
                .valueFormat(d3.format(',f'))
                .forceY([0, 10])
                .noData(gettext("(no errors over the given date range)"));
            self.error_count_chart.yAxis.tickFormat(d3.format(',f'));
        };

        self.update = function(values) {
            self.last_refresh_time(values.last_refresh_time);
            self.queued_sms_count(values.queued_sms_count);
            self.uses_restricted_time_windows(values.uses_restricted_time_windows);
            self.within_allowed_sms_times(values.within_allowed_sms_times);
            self.sms_resume_time(values.sms_resume_time);
            self.project_timezone(values.project_timezone);
            self.outbound_sms_sent_today(values.outbound_sms_sent_today);
            self.daily_outbound_sms_limit(values.daily_outbound_sms_limit);
            self.events_pending(values.events_pending);
        };

        self.update_charts = function(values) {
            d3.select('#sms_count_chart svg')
                .datum(values.sms_count_data)
                .transition()
                .duration(500)
                .call(self.sms_count_chart);
            nv.utils.windowResize(self.sms_count_chart.update);

            d3.select('#event_count_chart svg')
                .datum(values.event_count_data)
                .transition()
                .duration(500)
                .call(self.event_count_chart);
            nv.utils.windowResize(self.event_count_chart.update);

            d3.select('#error_count_chart svg')
                .datum(values.error_count_data)
                .transition()
                .duration(500)
                .call(self.error_count_chart);
            nv.utils.windowResize(self.error_count_chart.update);
        };
    };

    var dashboardViewModel = new DashboardViewModel();
    dashboardViewModel.init();

    var updateDashboard = function() {
        $.getJSON(dashboardUrl, {action: 'raw'})
            .done(function(json) {
                dashboardViewModel.update(json);
                if(!dashboardViewModel.bindingApplied()) {
                    // We have to do this on the async ajax thread otherwise there
                    // still might be a flicker on the page.
                    $('#messaging_dashboard').koApplyBindings(dashboardViewModel);
                    dashboardViewModel.bindingApplied(true);
                }
                // updating charts must be done when everything is visible
                dashboardViewModel.update_charts(json);
            })
            .always(function() {
                setTimeout(updateDashboard, 30000);
            });
    };

    $(function() {
        updateDashboard();
    });
});
