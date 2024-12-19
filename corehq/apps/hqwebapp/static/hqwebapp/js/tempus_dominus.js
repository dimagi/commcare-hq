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
    if (!window.USE_WEBPACK) {
        window.Popper = Popper;
    }

    let createDatePicker = function (el, options) {
        let picker = new tempusDominus.TempusDominus(el, _addDefaultOptions(options, {
            display: {
                theme: 'light',
                components: {
                    clock: false,
                },
            },
            localization: _.extend(defaultTranslations, {
                format: 'yyyy-MM-dd',
            }),
        }));

        if (options.viewDate) {
            picker.dates.setValue(options.viewDate);
        }

        // Since picking a date is a single-click action, hide the picker on date selection
        picker.subscribe("change.td", function () {
            picker.hide();
        });

        $(el).on("error.td", function (e) {
            picker.dates.setValue(null);
            e.stopPropagation();
        });

        return picker;
    };

    // This replaces createBootstrap3DefaultDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDefaultDateRangePicker = function (el, start, end) {
        return createDateRangePicker(el, getDateRangeSeparator(), start, end);
    };

    // This replaces createDateRangePicker in hqwebapp/js/daterangepicker.config
    let createDateRangePicker = function (el, separator, start, end) {
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

        if (start && end) {
            picker.dates.setValue(new tempusDominus.DateTime(start), 0);
            picker.dates.setValue(new tempusDominus.DateTime(end), 1);
        }


        // Handle single-date ranges
        picker.subscribe("hide.td", function () {
            if (picker.dates.picked.length === 1) {
                picker.dates.setValue(picker.dates.picked[0], 0);
                picker.dates.setValue(picker.dates.picked[0], 1);
            }
        });

        return picker;
    };

    let createTimePicker = function (el, options) {
        var picker = new tempusDominus.TempusDominus(el, _addDefaultOptions(options, {
            display: {
                theme: 'light',
                components: {
                    calendar: false,
                },
            },
            localization: _.extend(defaultTranslations, {
                hourCycle: 'h23',
                format: 'H:mm',
            }),
        }));

        if (options.viewDate) {
            picker.dates.setValue(options.viewDate);
        }

        $(el).on("error.td", function (e) {
            picker.dates.setValue(null);
            e.stopPropagation();
        });

        return picker;
    };

    // Combine user-passed TD options with default options.
    // A shallow extend is insufficient because TD options can be nested.
    // A truly generic deep extension is complex, so cheat based on what
    // we know about TD options: it's an object, but at most two levels,
    // and values are either primitives or objects, no arrays.
    let _addDefaultOptions = function (options, defaults) {
        options = options || {};
        Object.keys(defaults).forEach((key) => {
            if (!Object.hasOwn(options, key)) {
                options[key] = defaults[key];
            } else {
                if (options[key] && typeof(options[key]) === "object") {
                    Object.keys(defaults[key]).forEach((innerKey) => {
                        if (!Object.hasOwn(options[key], innerKey)) {
                            options[key][innerKey] = defaults[key][innerKey];
                        }
                    });
                }
            }
        });
        return options;
    };

    let getDateRangeSeparator = function () {
        return gettext(' to ');
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
