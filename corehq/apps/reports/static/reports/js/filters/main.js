hqDefine("reports/js/filters/main", [
    'jquery',
    'knockout',
    'hqwebapp/js/main',
    'reports/js/standard_hq_report',
    'reports/js/filters/select2s',
    'reports/js/filters/phone_number',
    'reports/js/filters/button_group',
    'reports/js/filters/schedule_instance',
    'locations/js/location_drilldown',
    'reports_core/js/choice_list_utils',
    'select2-3.5.2-legacy/select2',
], function(
    $,
    ko,
    hqMain,
    standardHQReportModule,
    select2Filter,
    phoneNumberFilter,
    buttonGroup,
    scheduleInstanceFilter,
    locationDrilldown,
    choiceListUtils
) {
    var init = function() {
        // Datespans
        $('.report-filter-datespan').each(function() {
            var $filterRange = $(this);
            if ($filterRange.data("init")) {
                var separator = $filterRange.data('separator');
                var reportLabels = $filterRange.data('reportLabels');
                var standardHQReport = standardHQReportModule.getStandardHQReport();

                $filterRange.createDateRangePicker(
                    reportLabels, separator,
                    $filterRange.data('startDate'),
                    $filterRange.data('endDate')
                );
                $filterRange.on('change apply', function() {
                    var dates = $(this).val().split(separator);
                    $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.startdate', dates[0]);
                    $('#report_filter_datespan_startdate').val(dates[0]);
                    $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.enddate', dates[1]);
                    $('#report_filter_datespan_enddate').val(dates[1]);
                });
            }
        });

        // other Datespans *groan* TODO unify on this one
        $('.report-filter-datespan-filter').each(function(i, el) {
            var $el = $(el), data = $el.data();
            var $filterStart = $("#" + data.cssId + "-start");
            var $filterEnd = $("#" + data.cssId + "-end");

            $el.createBootstrap3DefaultDateRangePicker();
            $el.on('apply change', function () {
                var separator = $().getDateRangeSeparator();
                var dates = $el.val().split(separator);
                $filterStart.val(dates[0]);
                $filterEnd.val(dates[1]);
            });

            if (!$el.val() && $filterStart.val() && $filterEnd.val()) {
                var text = $filterStart.val() + $().getDateRangeSeparator() + $filterEnd.val();
                $el.val(text);
            } else if (!$el.val()) {
                $el.val(gettext("Show All Dates"));
            }
        });

        // Date selector
        var $dateSelector = $("#filter_date_selector");
        if ($dateSelector.length && $dateSelector.data("init")) {
            $('#filter_date_selector').daterangepicker(
                {
                    locale: {
                        format: 'YYYY-MM-DD',
                    },
                    singleDatePicker: true,
                }
            );
        }

        // Date ranges (used in accounting)
        $('.date-range').each(function() {
            $(this).datepicker({
                changeMonth: true,
                changeYear: true,
                dateFormat: 'yy-mm-dd',
            });
        });

        // Optional date ranges, optional month+year (used in accounting)
        $(".report-filter-optional").each(function() {
            $(this).koApplyBindings({
                showFilterName: ko.observable($(this).data("showFilterName")),
            });
        });

        // Selects
        $('.report-filter-single-option').each(function() {
            select2Filter.initSingle(this);
        });
        $('.report-filter-single-option-paginated').each(function() {
            select2Filter.initSinglePaginated(this);
        });
        $('.report-filter-multi-option').each(function() {
            select2Filter.initMulti(this);
        });

        // Submission type (Raw Forms, Errors, & Duplicates)
        $('.report-filter-button-group').each(function() {
            buttonGroup.link(this);
        });

        // Tags (to filter by CC version in global device logs soft asserts report)
        $('.report-filter-tags').each(function() {
            $(this).select2({tags: $(this).data("tags"), allowClear: true});
        });

        // Initialize any help bubbles
        $('.hq-help-template').each(function () {
            hqMain.transformHelpTemplate($(this), true);
        });

        $(".report-filter-message-type-configuration").each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            var model = scheduleInstanceFilter.model(data.initialValue, data.conditionalAlertChoices);
            $el.koApplyBindings(model);

            $('[name=rule_id]').each(function(i, el) {
                $(el).select2({
                    allowClear: true,
                    placeholder: gettext("All"),
                });
            });
        });
        $(".report-filter-phone-number").each(function (i, el) {
            var $el = $(el),
                data = $el.data();
            var model = phoneNumberFilter.model(data.initialValue, data.groups);
            $el.koApplyBindings(model);
        });
        $('[name=selected_group]').each(function(i, el) {
            $(el).select2({
                allowClear: true,
                placeholder: gettext("Select a group"),
            });
        });
        $('.report-filter-location-async').each(function(i, el) {
            var $el = $(el), data = $el.data();
            var model = locationDrilldown.locationSelectViewModel({
                "hierarchy": data.hierarchy,
                "show_location_filter": data.makeOptional && !data.locId ? "n" : "y",
                "loc_url": data.locationUrl,
                "auto_drill": data.autoDrill,
                "max_drilldown_length": data.maxDrilldownLength,
            });
            $el.koApplyBindings(model);
            model.load(data.locs, data.locId);
        });
        $('.report-filter-logtag').each(function(i, el) {
            var $el = $(el), data = $el.data();
            if (data.defaultOn) {
                $el.attr("name", "");
                $el.change(function () {
                    $el.attr("name", "logtag");
                });
            }
            if (data.errorOnly) {
                $("#device-log-errors-only-checkbox").change(function () {
                    var multiSelect = $el;
                    if ($el.prop('checked')) {
                        $el.attr("name", "errors_only");
                        multiSelect.attr("name", "");
                        multiSelect.addClass("hide");
                    } else {
                        $el.attr("name", "");
                        if (!data.defaultOn) {
                            multiSelect.attr("name", "logtag");
                        }
                        multiSelect.removeClass("hide");
                    }
                });
            }
        });

        $('.report-filter-dynamic-choice-list').each(function (i, el) {
            var $el = $(el), data = $el.data();
            var initialValues = _.map(data.initialValues, function(value) {
                    return choiceListUtils.formatValueForSelect2(value);
                }),
                // TODO: Ideally the separator would be defined in one place. Right now it is
                //       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
                separator = "\u001F";

            $el.select2({
                minimumInputLength: 0,
                multiple: true,
                separator: separator,
                allowClear: true,
                // allowClear only respected if there is a non empty placeholder
                placeholder: " ",
                ajax: {
                    url: data.ajaxFilterUrl,
                    dataType: 'json',
                    quietMillis: 250,
                    data: choiceListUtils.getApiQueryParams,
                    results: choiceListUtils.formatPageForSelect2,
                    cache: true,
                },
            });
            $el.select2('data', initialValues);
        });
    };

    return {
        init: init,
    };
});
