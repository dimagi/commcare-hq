hqDefine("reports/js/filters/main", [
    'jquery',
    'knockout',
    'hqwebapp/js/main',
    'reports/js/standard_hq_report',
    'reports/js/filters/select2s',
    'reports/js/filters/phone_number',
    'reports/js/filters/button_group',
    'reports/js/filters/schedule_instance',
    'select2-3.5.2-legacy/select2',
], function(
    $,
    ko,
    hqMain,
    standardHQReportModule,
    select2Filter,
    phoneNumberFilter,
    buttonGroup,
    scheduleInstanceFilter
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
            select2Filter.initMulti(this);
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
    };

    return {
        init: init,
    };
});
