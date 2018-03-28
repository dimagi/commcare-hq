/* globals d3, nv, ko */
hqDefine("scheduling/js/dashboard", function() {
    var dashboardUrl = hqImport("hqwebapp/js/initial_page_data").reverse("messaging_dashboard");

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
        }
    };

    var dashboardViewModel = new DashboardViewModel();

    var updateDashboard = function() {
        $.getJSON(dashboardUrl, {action: 'raw'}).done(function(json) {
            dashboardViewModel.update(json);
            if(!dashboardViewModel.bindingApplied()) {
                // We have to do this on the async ajax thread otherwise there
                // still might be a flicker on the page.
                $('#messaging_dashboard').koApplyBindings(dashboardViewModel);
                dashboardViewModel.bindingApplied(true);
            }
        });
        setTimeout(updateDashboard, 30000);
    }

    $(function() {
        updateDashboard();
    });
});
