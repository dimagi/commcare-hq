hqDefine("enterprise/js/project_dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap5/alert_user',
    'analytix/js/kissmetrix',
    'hqwebapp/js/tempus_dominus',
    'moment',
    'hqwebapp/js/bootstrap5/hq.helpers',
    'hqwebapp/js/components/select_toggle',
    'commcarehq',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser,
    kissmetrics,
    tempusDominus,
    moment
) {
    const PRESET_LAST_30 = "last_30";
    const PRESET_PREV_MONTH = "prev_month";
    const PRESET_CUSTOM = "custom";

    const dateRangePresetOptions = [
        {id: PRESET_LAST_30, text: gettext("Last 30 Days")},
        {id: PRESET_PREV_MONTH, text: gettext("Previous Month")},
        {id: PRESET_CUSTOM, text: gettext("Custom")},
    ];

    var MobileFormSubmissionsTile = function (datePicker) {
        var self = {};
        self.endDate = ko.observable(moment().utc());
        self.startDate = ko.observable(self.endDate().clone().subtract(30, "days"));
        self.presetType = ko.observable(PRESET_LAST_30);
        self.customDateRangeDisplay = ko.observable(datePicker.optionsStore.input.value);

        self.presetText = ko.pureComputed(function () {
            if (self.presetType() !== PRESET_CUSTOM) {
                return dateRangePresetOptions.find(ele => ele.id === self.presetType()).text;
            } else {
                return self.customDateRangeDisplay();
            }
        });

        self.onApply = function (preset, startDate, endDate) {
            self.startDate(startDate);
            self.endDate(endDate);
            self.presetType(preset);
            self.customDateRangeDisplay(datePicker.optionsStore.input.value);

            updateDisplayTotal($("#form_submissions"), {
                "start_date": startDate.toISOString(),
                "end_date": endDate.toISOString(),
            });
        };

        return self;
    };

    var SMSTile = function (datePicker) {
        var self = {};
        self.endDate = ko.observable(moment().utc());
        self.startDate = ko.observable(self.endDate().clone().subtract(30, "days"));
        self.presetType = ko.observable(PRESET_LAST_30);
        self.customDateRangeDisplay = ko.observable(datePicker.optionsStore.input.value);

        self.presetText = ko.pureComputed(function () {
            if (self.presetType() !== PRESET_CUSTOM) {
                return dateRangePresetOptions.find(ele => ele.id === self.presetType()).text;
            } else {
                return self.customDateRangeDisplay();
            }
        });

        self.onApply = function (preset, startDate, endDate) {
            self.startDate(startDate);
            self.endDate(endDate);
            self.presetType(preset);
            self.customDateRangeDisplay(datePicker.optionsStore.input.value);

            updateDisplayTotal($("#sms"), {
                "start_date": startDate.toISOString(),
                "end_date": endDate.toISOString(),
            });
        };

        return self;
    };

    var DateRangeModal = function ($modal, datePicker, presetOptions, maxDateRangeDays, tileMap) {
        let tileDisplay = null;
        $modal.on('show.bs.modal', function (event) {
            var button = $(event.relatedTarget);
            tileDisplay = tileMap[button.data('sender')];

            self.presetType(tileDisplay.presetType());
            self.customStartDate(tileDisplay.startDate().clone());
            self.customEndDate(tileDisplay.endDate().clone());
        });

        var self = {};
        self.presetOptions = presetOptions;
        self.presetType = ko.observable(PRESET_LAST_30);
        self.displayCustom = ko.pureComputed(function () {
            return self.presetType() === PRESET_CUSTOM;
        });

        self.clarifyingText = ko.pureComputed(function () {
            const template = _.template('<i class="fa-solid fa-info-circle"></i> ' + gettext("Spans <%- startDate %> to <%- endDate %> (UTC)"));
            return template({
                startDate: self.startDate().format("YYYY-MM-DD"),
                endDate: self.endDate().format("YYYY-MM-DD"),
            });
        });

        self.customStartDate = ko.observable(datePicker.dates.picked[0]);
        self.customEndDate = ko.observable(datePicker.dates.picked[1]);

        const updateWidgetDates = function (startDate, endDate) {
            datePicker.dates.clear();
            datePicker.dates.setValue(new tempusDominus.tempusDominus.DateTime(startDate));
            datePicker.dates.setValue(new tempusDominus.tempusDominus.DateTime(endDate), 1);
            self.customStartDate(startDate);
            self.customEndDate(endDate);
        };

        /*
        NOTE: The `.local(true)` calls below are due to TempusDominus only supporting local time.
        These calls change the datetime to the local timezone without adjusting the displayed date,
        so the displayed UTC datetime will still display as the same string within TempusDominus.
        */
        self.onApply = function () {
            if (self.presetType() !== PRESET_CUSTOM) {
                // update the custom values to align with the selected preset, for opening the modal in the future
                updateWidgetDates(self.startDate().clone().local(true), self.endDate().clone().local(true));
            }
            tileDisplay.onApply(self.presetType(), self.startDate(), self.endDate());
        };

        self.onCancel = function () {
            self.presetType(tileDisplay.presetType());
            const startDate = tileDisplay.startDate().clone();
            const endDate = tileDisplay.endDate().clone();
            if (tileDisplay.presetType() !== PRESET_CUSTOM) {
                startDate.local(true);
                endDate.local(true);
            }
            updateWidgetDates(startDate, endDate);
        };

        self.endDate = ko.pureComputed(function () {
            const presetType = self.presetType();
            let endDate = null;
            if (presetType === PRESET_LAST_30) {
                endDate = moment().utc();
            } else if (presetType === PRESET_PREV_MONTH) {
                endDate = moment().utc().subtract(1, "months").endOf("month");
            } else {
                endDate = moment(self.customEndDate());
            }

            // the backend handles inclusive date ranges by adding a full day to the end date,
            // so we'd like to minimize the results shown from the next day
            return endDate.startOf('day');
        });

        self.startDate = ko.pureComputed(function () {
            const presetType = self.presetType();
            let startDate = null;
            if (presetType === PRESET_LAST_30) {
                startDate = self.endDate().clone().subtract(30, "days");
            } else if (presetType === PRESET_PREV_MONTH) {
                startDate = self.endDate().clone().startOf("month");
            } else {
                startDate = moment(self.customStartDate());
            }

            return startDate;
        });

        datePicker.subscribe("change.td", function () {
            if (datePicker.dates.picked.length === 1) {
                const selectedDate = moment(datePicker.dates.picked[0]);
                datePicker.updateOptions({
                    restrictions: {
                        minDate: new tempusDominus.tempusDominus.DateTime(selectedDate.clone().subtract(maxDateRangeDays, 'days')),
                        maxDate: new tempusDominus.tempusDominus.DateTime(selectedDate.clone().add(maxDateRangeDays, 'days')),
                    },
                });
            } else {
                datePicker.updateOptions({
                    restrictions: {
                        minDate: undefined,
                        maxDate: undefined,
                    },
                });
            }
            self.customStartDate(datePicker.dates.picked[0]);
            if (datePicker.dates.picked.length > 1) {
                self.customEndDate(datePicker.dates.picked[1]);
            } else {
                self.customEndDate(datePicker.dates.picked[0]);
            }
        });

        return self;
    };

    function localizeNumberlikeString(input) {
        if ((typeof input === "string") && (input.endsWith('%'))) {
            const number = input.slice(0, -1);
            return Number(number).toLocaleString(
                undefined,
                {minimumFractionDigits: 1,  maximumFractionDigits: 1}
            ) + '%';
        } else {
            return Number(input).toLocaleString();
        }
    }

    function updateDisplayTotal($element, kwargs) {
        const $display = $element.find(".total");
        const slug = $element.data("slug");
        const requestParams = {
            url: initialPageData.reverse("enterprise_dashboard_total", slug),
            success: function (data) {
                $display.html(localizeNumberlikeString(data.total));
            },
            error: function (request) {
                if (request.responseJSON) {
                    alertUser.alert_user(request.responseJSON["message"], "danger");
                } else {
                    alertUser.alert_user(gettext("Error updating display total, please try again or report an issue if this persists."), "danger");
                }
                $display.html(gettext("??"));
            },
            data: kwargs,
        };
        $display.html('<i class="fa fa-spin fa-spinner"></i>');
        $.ajax(requestParams);
    }

    $(function () {
        const metricType = initialPageData.get('metric_type');
        const datePicker = tempusDominus.createDefaultDateRangePicker(
            document.getElementById("id_date_range"),
            moment().subtract(30, "days"),
            moment()
        );

        const $dateRangeModal = $('#enterpriseFormsDaterange');

        const formSubmissionsDisplay = MobileFormSubmissionsTile(datePicker);
        const smsDisplay = SMSTile(datePicker);
        const maxDateRangeDays = initialPageData.get("max_date_range_days");

        const displayMap = {
            "form_submission": formSubmissionsDisplay,
            "sms": smsDisplay,
        };
        const dateRangeModal = DateRangeModal($dateRangeModal, datePicker, dateRangePresetOptions, maxDateRangeDays, displayMap);

        $("#form_submission_dateRangeDisplay").koApplyBindings(formSubmissionsDisplay);
        $("#sms_dateRangeDisplay").koApplyBindings(smsDisplay);
        $dateRangeModal.koApplyBindings(
            dateRangeModal
        );

        kissmetrics.track.event(`[${metricType}] Visited page`);
        $(".report-panel").each(function () {
            var $element = $(this),
                slug = $element.data("slug");

            updateDisplayTotal($element);

            $element.find(".btn-primary").click(function () {
                kissmetrics.track.event(`[${metricType}] Clicked Email Report for ` + slug);
                var $button = $(this);
                $button.disableButton();
                const requestParams = {
                    url: initialPageData.reverse("enterprise_dashboard_email", slug),
                    success: function (data) {
                        alertUser.alert_user(data.message, "success");
                        $button.enableButton();
                    },
                    error: function (request) {
                        if (request.responseJSON) {
                            alertUser.alert_user(request.responseJSON["message"], "danger");
                        } else {
                            alertUser.alert_user(gettext("Error sending email, please try again or report an issue if this persists."), "danger");
                        }
                        $button.enableButton();
                    },
                };

                const dateRangeSlugs = ["form_submissions", "sms"];
                if (dateRangeSlugs.includes(slug)) {
                    requestParams["data"] = {
                        "start_date": dateRangeModal.startDate().toISOString(),
                        "end_date": dateRangeModal.endDate().toISOString(),
                    };
                }
                $.ajax(requestParams);
            });
        });
    });
});
