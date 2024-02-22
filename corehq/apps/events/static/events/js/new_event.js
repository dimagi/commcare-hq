hqDefine("events/js/new_event", [
    "jquery",
    "knockout",
    "hqwebapp/js/multiselect_utils",
    "hqwebapp/js/initial_page_data",
    "locations/js/widgets",
    "hqwebapp/js/bootstrap3/widgets",
    "jquery-ui/ui/widgets/datepicker",
], function (
    $,
    ko,
    multiselectUtils,
    initialPageData,
    locationsWidgets
) {
    $(function () {
        const ATTENDEE_PROPS = {
            selectableHeaderTitle: gettext('Possible Attendees'),
            selectedHeaderTitle: gettext('Expected Attendees'),
            searchItemTitle: gettext('Search Attendees'),
        };
        const ATTENDANCE_TAKER_PROPS = {
            selectableHeaderTitle: gettext('Possible Attendance Takers'),
            selectedHeaderTitle: gettext('Selected Attendance Takers'),
            searchItemTitle: gettext('Search Attendance Takers'),
        };

        $("#id_start_date").datepicker({
            dateFormat: "yy-mm-dd",
            minDate: 0,
        });

        $("#id_end_date").datepicker({
            dateFormat: "yy-mm-dd",
            minDate: 0,
        });

        multiselectUtils.createFullMultiselectWidget('id_expected_attendees', ATTENDEE_PROPS);

        multiselectUtils.createFullMultiselectWidget('id_attendance_takers', ATTENDANCE_TAKER_PROPS);

        function eventViewModel(initialData) {
            'use strict';
            var self = {};

            // Disable the submit button unless attendance takers are present
            var submitBtn = $('input[id="submit-id-submit_btn"]');
            var attendanceTakers = $('#id_attendance_takers');

            var initialAttendanceTakers = initialData.attendance_takers;
            submitBtn.prop('disabled', !initialAttendanceTakers || initialAttendanceTakers.length === 0);
            attendanceTakers.on('change', function () {
                var attendanceTakersLength = attendanceTakers.val().length;
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

            self.locationId.subscribe(function (newLocation) {
                function rebuildList(elementId, data) {
                    const $expectedList = $(`#${elementId}`);
                    $expectedList.empty();
                    for (const item of data) {
                        $expectedList.append(
                            `<option value="${item.id}">${item.name}</option>`
                        );
                    }
                }

                $.ajax({
                    url: initialPageData.reverse('get_attendees_and_attendance_takers'),
                    method: 'GET',
                    data: {
                        'location_id': newLocation,
                    },
                    success: function (data) {
                        $("#attendance-list-error").addClass("hidden");

                        rebuildList("id_expected_attendees", data.attendees);
                        rebuildList("id_attendance_takers", data.attendance_takers);
                        multiselectUtils.rebuildMultiselect('id_expected_attendees', ATTENDEE_PROPS);
                        multiselectUtils.rebuildMultiselect('id_attendance_takers', ATTENDANCE_TAKER_PROPS);
                    },
                    error: function () {
                        $("#attendance-list-error").removeClass("hidden");
                    },
                });
            });

            return self;
        }

        var eventModel = eventViewModel(initialPageData.get('current_values'));
        $('#tracking-event-form').koApplyBindings(eventModel);
    });
});
