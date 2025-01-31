hqDefine("reports/js/filters/schedule_instance", [
    'jquery',
    'knockout',
    'bootstrap-daterangepicker/daterangepicker',
], function (
    $,
    ko,
) {
    var model = function (initial, conditionalAlertChoices) {
        var self = {};
        var all = [{'id': '', 'name': gettext('All')}];
        self.date_selector_type = ko.observable(initial.date_selector_type);
        self.next_event_due_after = ko.observable(initial.next_event_due_after);
        self.configuration_type = ko.observable(initial.configuration_type);
        self.rule_id = ko.observable(initial.rule_id);
        self.conditional_alert_choices = ko.observableArray(all.concat(conditionalAlertChoices));
        self.active = ko.observable(initial.active);
        self.case_id = ko.observable(initial.case_id);

        $(function () {
            $('#id_next_event_due_after').daterangepicker(
                {
                    locale: {
                        format: 'YYYY-MM-DD',
                    },
                    singleDatePicker: true,
                },
            );
        });

        return self;
    };

    return {
        model: model,
    };
});
