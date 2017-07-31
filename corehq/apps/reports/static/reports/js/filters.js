/* globals COMMCAREHQ */
hqDefine("reports/js/filters.js", function() {
    var linkButtonGroup = function (groupIdOrEl, can_be_empty) {
        // this is used to initialize the buttongroup filters
        // see the user filter for sample usage.
        var $el = typeof groupIdOrEl === "string" ? $("#" + groupIdOrEl) : $(groupIdOrEl);
        $el.find("button").click(function(e) {
            e.preventDefault();
            var $activeCheckbox = $('#'+$(this).data("checkfilter"));

            if($(this).hasClass('active')) {
                $(this).addClass('btn-success');
                $activeCheckbox.prop("checked", true);
            } else {
                $(this).removeClass('btn-success');
                $activeCheckbox.prop("checked", false);
            }
            $activeCheckbox.trigger('change');

            if((!$el.children().hasClass('btn-success')) && !can_be_empty) {
                var $firstChild = $el.children().first();
                $firstChild.addClass('btn-success');
                $('#'+$firstChild.data("checkfilter")).prop("checked", true);
                if ($(this).data("checkfilter") !== $firstChild.data("checkfilter")) {
                    $firstChild.removeClass('active');
                } else {
                    return false;
                }
            }
        });
    };

    var init = function() {
        // Datespans
        $('.report-filter-datespan').each(function() {
            var $filterRange = $(this);
            if ($filterRange.data("init")) {
                var separator = $filterRange.data('separator');
                var report_labels = $filterRange.data('reportLabels');
                var standardHQReport = hqImport("reports/js/standard_hq_report.js").getStandardHQReport();

                $filterRange.createDateRangePicker(
                    report_labels, separator,
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
        $('.date-range').datepicker({
            changeMonth: true,
            changeYear: true,
            dateFormat: 'yy-mm-dd',
        });

        // Optional date ranges, optional month+year (used in accounting)
        $(".report-filter-optional").each(function() {
            $(this).koApplyBindings({
                showFilterName: ko.observable($(this).data("showFilterName")),
            });
        });

        // Submission type (Raw Forms, Errors, & Duplicates)
        $('.report-filter-button-group').each(function() {
            linkButtonGroup(this);
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
