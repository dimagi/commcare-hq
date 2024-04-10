/**
  * This replaces hqwebapp/js/daterangepicker.config, which is tied to bootstrap3
  *
  * It does not yet support predefined date ranges, which are not natively supported in tempus dominus.
  * It also does not support a default date range, as tempus dominus's defaultDate only supports one date.
  */
hqDefine("hqwebapp/js/tempus_dominus", [
    'underscore',
    'popper',
    'tempusDominus',
    'hqwebapp/js/initial_page_data',
], function (
    _,
    Popper,
    tempusDominus,
    initialPageData
) {
    // https://github.com/Eonasdan/tempus-dominus/discussions/2698
    window.Popper = Popper;

    // This replaces createBootstrap3DefaultDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDefaultDateRangePicker = function (el) {
        return createDateRangePicker(el, getDateRangeSeparator());
    };

    // This replaces createDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDateRangePicker = function (el, separator) {
        return new tempusDominus.TempusDominus(
            el, {
                dateRange: true,
                multipleDatesSeparator: separator,
                display: {
                    theme: 'light',
                    components: {
                        clock: false,
                        year: true,
                    },
                    buttons: {
                        clear: !!initialPageData.get('daterangepicker-show-clear'),
                        close: true,
                    },
                },
                localization: _.extend(defaultTranslations, {
                    format: 'yyyy-MM-dd',
                }),
            },
        );
    };

    let getDateRangeSeparator = function () {
        return ' to ';
    };

    const defaultTranslations = {
        clear: gettext('Clear selection'),
        close: gettext('Close the picker'),
        dayViewHeaderFormat: { month: gettext('long'), year: gettext('2-digit') },
        decrementHour: gettext('Decrement Hour'),
        decrementMinute: gettext('Decrement Minute'),
        decrementSecond: gettext('Decrement Second'),
        incrementHour: gettext('Increment Hour'),
        incrementMinute: gettext('Increment Minute'),
        incrementSecond: gettext('Increment Second'),
        nextCentury: gettext('Next Century'),
        nextDecade: gettext('Next Decade'),
        nextMonth: gettext('Next Month'),
        nextYear: gettext('Next Year'),
        pickHour: gettext('Pick Hour'),
        pickMinute: gettext('Pick Minute'),
        pickSecond: gettext('Pick Second'),
        previousCentury: gettext('Previous Century'),
        previousDecade: gettext('Previous Decade'),
        previousMonth: gettext('Previous Month'),
        previousYear: gettext('Previous Year'),
        selectDate: gettext('Select Date'),
        selectDecade: gettext('Select Decade'),
        selectMonth: gettext('Select Month'),
        selectTime: gettext('Select Time'),
        selectYear: gettext('Select Year'),
        today: gettext('Go to today'),
        toggleMeridiem: gettext('Toggle Meridiem'),
    };

    return {
        createDateRangePicker: createDateRangePicker,
        createDefaultDateRangePicker: createDefaultDateRangePicker,
        getDateRangeSeparator: getDateRangeSeparator,
    };
});
