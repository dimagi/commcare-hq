hqDefine("up_nrhm/js/main", function () {
    function hideFilters(sf) {
        if (sf === "" || sf === 'sf2') {
            $('#fieldset_datespan').css('display', 'block');
            $('#fieldset_year').css('display', 'none');
            $('#fieldset_month').css('display', 'none');
            $('#report_filter_hierarchy_af').parent().parent().removeClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf3") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().removeClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf4") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().addClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf5") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().addClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().addClass('hideImportant');
        }
    }

    $(function () {
        if (hqImport("hqwebapp/js/initial_page_data").get("rendered_as") === "print") {
            if (!$('#report_filter_sf').val()) {
                document.body.style.zoom="80%";
                $('.hq-loading').hide();
            }
        }

        $('#report_filter_sf').on('change', function() {
            sf = $(this).val();
            hideFilters(sf);
        });
        $('#hq-report-filters').on('change', function() {
            hideFilters(sf);
        });
        sf = $('#report_filter_sf').val();
        hideFilters(sf);

        // Datespan handling
        var $datespan = $('#filter_range');
        var separator = $datespan.data("separator");
        var report_labels = $datespan.data("report-labels");
        var standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();

        $('#filter_range').createDateRangePicker(
            report_labels,
            separator,
            $datespan.data("start-date").toISOString().split("T")[0],
            $datespan.data("end-date").toISOString().split("T")[0]
        );
        $('#filter_range').on('change apply', function() {
            picker = $(this).data('daterangepicker');
            var diffDays = moment.duration(picker.endDate.diff(picker.startDate)).asDays();
            if (diffDays > 31) {
                var startDate = picker.endDate.clone();
                picker.setStartDate(startDate.subtract('days', 31));
                var inputVal = picker.startDate.format('YYYY-MM-DD') + separator + picker.endDate.format('YYYY-MM-DD');
                $(this).val(inputVal)
            }

            var dates = $(this).val().split(separator);
            $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.startdate', dates[0]);
            $('#report_filter_datespan_startdate').val(dates[0]);
            $(standardHQReport.filterAccordion).trigger('hqreport.filter.datespan.enddate', dates[1]);
            $('#report_filter_datespan_enddate').val(dates[1]);
        });
    });
});
