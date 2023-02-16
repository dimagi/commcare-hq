hqDefine("events/js/new_event", [
    "jquery",
    "knockout",
    "hqwebapp/js/widgets",
    "jquery-ui/ui/widgets/datepicker",
    "hqwebapp/js/components.ko",
], function (
    $,
    ko,
) {
    $(function () {
        $("#id_start_date").datepicker({
            dateFormat: "yy-mm-dd",
            minDate: 0,
        });

        $("#id_end_date").datepicker({
            dateFormat: "yy-mm-dd",
            minDate: 0,
        });


        function eventViewModel() {
            'use strict';
            var self = {};

            self.name = ko.observable();
            self.startDate = ko.observable();
            self.endDate = ko.observable();
            self.attendanceTarget = ko.observable(1);
            self.sameDayRegistration = ko.observable();
            self.trackingOption = ko.observable("by_day");

            self.showTrackingOptions = ko.computed(function() {
                var startDateValue = self.startDate();
                var endDateValue = self.endDate();

                if (startDateValue && endDateValue) {
                    return startDateValue !== endDateValue;
                }
                return false;
            });

            return self;
        }

        var eventModel = eventViewModel();
        $('#tracking-event-form').koApplyBindings(eventModel);
    });
});
