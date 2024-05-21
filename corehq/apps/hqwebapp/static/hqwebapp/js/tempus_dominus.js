"use strict";
/**
  * This replaces hqwebapp/js/daterangepicker.config, which is tied to bootstrap3
  *
  * It does not yet support predefined date ranges, which are not natively supported in tempus dominus.
  * It also does not yet support a default date range.
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

    let createDatePicker = function (el, extraOptions) {
        return new tempusDominus.TempusDominus(el, _.extend({
            display: {
                theme: 'light',
                components: {
                    clock: false,
                },
            },
            localization: _.extend(defaultTranslations, {
                format: _getFormat(extraOptions, 'yyyy-MM-dd'),
            }),
        }, extraOptions || {}));
    };

    // This replaces createBootstrap3DefaultDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDefaultDateRangePicker = function (el) {
        return createDateRangePicker(el, getDateRangeSeparator());
    };

    // This replaces createDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDateRangePicker = function (el, separator) {
        let picker = new tempusDominus.TempusDominus(
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
            }
        );

        // Handle single-date ranges
        picker.subscribe("hide.td", function () {
            if (picker.dates.picked.length === 1) {
                picker.dates.setValue(picker.dates.picked[0], 0);
                picker.dates.setValue(picker.dates.picked[0], 1);
            }
        });
    };

    let createTimePicker = function (el, extraOptions) {
        return new tempusDominus.TempusDominus(el, _.extend({
            display: {
                theme: 'light',
                components: {
                    calendar: false,
                },
            },
            localization: _.extend(defaultTranslations, {
                format: 'yyyy-MM-dd',
            }),
        }, extraOptions || {}));
    };

    let _getFormat = function (options, defaultFormat) {
        if (options && options.localization && options.localization.format) {
            return options.localization.format;
        }
        return defaultFormat;
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
        createDatePicker: createDatePicker,
        createDateRangePicker: createDateRangePicker,
        createDefaultDateRangePicker: createDefaultDateRangePicker,
        createTimePicker: createTimePicker,
        getDateRangeSeparator: getDateRangeSeparator,
        tempusDominus: tempusDominus,
    };
});
