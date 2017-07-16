hqDefine("reports/js/filters.js", function() {
    var init = function() {
        // Datespans
        var $filterRange = $('.report-filter-datespan');
        if ($filterRange.length && $filterRange.data("init")) {
            var separator = $filterRange.data('separator');
            var report_labels = $filterRange.data('reportLabels');
            var standardHQReport = hqImport("reports/js/standard_hq_report.js").getStandardHQReport();

            $filterRange.createDateRangePicker(
                report_labels, separator,
                $filterRange.data('startDate'),
                $filterRange.data('endDate')
            );
            $filterRange.on('change apply', function(ev, picker) {
                var dates = $(this).val().split(separator);
                $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.startdate', dates[0]);
                $('#report_filter_datespan_startdate').val(dates[0]);
                $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.enddate', dates[1]);
                $('#report_filter_datespan_enddate').val(dates[1]);
            });
        }

        // Date ranges (used in accounting)
        $('.date-range').datepicker({
            changeMonth: true,
            changeYear: true,
            dateFormat: 'yy-mm-dd',
        });

        // Initialize any help bubbles
        $('.hq-help-template').each(function () {
            COMMCAREHQ.transformHelpTemplate($(this), true);
        });
    };

    return {
        init: init,
    };
});
