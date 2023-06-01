hqDefine("events/js/new_event", [
    "jquery",
    "knockout",
    "hqwebapp/js/multiselect_utils",
    "hqwebapp/js/initial_page_data",
    "locations/js/widgets",
    "hqwebapp/js/widgets",
    "jquery-ui/ui/widgets/datepicker",
], function (
    $,
    ko,
    multiselectUtils,
    initialPageData,
    locationsWidgets
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

        multiselectUtils.createFullMultiselectWidget('id_expected_attendees', {
            selectableHeaderTitle: gettext('Possible Attendees'),
            selectedHeaderTitle: gettext('Expected Attendees'),
            searchItemTitle: gettext('Search Attendees'),
        });

        multiselectUtils.createFullMultiselectWidget('id_attendance_takers', {
            selectableHeaderTitle: gettext('Possible Attendance Takers'),
            selectedHeaderTitle: gettext('Selected Attendance Takers'),
            searchItemTitle: gettext('Search Attendance Takers'),
        });

        function eventViewModel(initialData) {
            'use strict';
            var self = {};

            // Disable the submit button unless attendance takers are present
            var submitBtn = $('input[type="submit"]');
            var attendanceTakers = $(id_attendance_takers);

            var initialAttendanceTakers = initialData.attendance_takers;
            submitBtn.prop('disabled', !initialAttendanceTakers || initialAttendanceTakers.length == 0);
            attendanceTakers.on('change', function() {
                var attendanceTakersLength = attendanceTakers.val().length
                submitBtn.prop('disabled', attendanceTakersLength === 0);
            });

            self.name = ko.observable(initialData.name);
            self.startDate = ko.observable(initialData.start_date);
            self.endDate = ko.observable(initialData.end_date);
            self.locationId = ko.observable(initialData.location_id);
            self.attendanceTarget = ko.observable(initialData.attendance_target || 1);
            self.sameDayRegistration = ko.observable(initialData.sameday_reg);
            self.trackingOption = ko.observable(initialData.tracking_option || "by_day");

            var $locationSelect = $("#id_location_id");
            if ($locationSelect.length) {
                locationsWidgets.initAutocomplete($locationSelect);
            }

            self.showTrackingOptions = ko.computed(function () {
                var startDateValue = self.startDate();
                var endDateValue = self.endDate();

                if (startDateValue && endDateValue) {
                    return startDateValue !== endDateValue;
                }
                return false;
            });

            return self;
        }

        var eventModel = eventViewModel(initialPageData.get('current_values'));
        $('#tracking-event-form').koApplyBindings(eventModel);
    });
});
