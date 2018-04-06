hqDefine("reports/js/filters/main", [
    'jquery',
    'knockout',
    'hqwebapp/js/main',
    'reports/js/standard_hq_report',
    'select2-3.5.2-legacy/select2',
], function(
    $,
    ko,
    hqMain,
    standardHQReportModule
) {
    var init = function() {
        // Datespans
        $('.report-filter-datespan').each(function() {
            var $filterRange = $(this);
            if ($filterRange.data("init")) {
                var separator = $filterRange.data('separator');
                var report_labels = $filterRange.data('reportLabels');
                var standardHQReport = standardHQReportModule.getStandardHQReport();

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
            var $filter = $(this);
            $filter.parent().koApplyBindings({
                select_params: $filter.data("selectOptions"),
                current_selection: ko.observable($filter.data("selected")),
            });
            $filter.select2();
        });
        $('.report-filter-single-option-paginated').each(function() {
            var $filter = $(this);
            $filter.select2({
                ajax: {
                    url: $filter.data('url'),
                    type: 'POST',
                    dataType: 'json',
                    quietMills: 250,
                    data: function (term, page) {
                        return {
                            q: term,
                            page: page,
                            handler: $filter.data('handler'),
                            action: $filter.data('action'),
                        };
                    },
                    results: function (data, page) {
                        if (data.success) {
                            var limit = data.limit;
                            var hasMore = (page * limit) < data.total;
                            return {
                                results: data.items,
                                more: hasMore,
                            };
                        } else {
                            console.log(data.error);
                        }
                    },
                },
                allowClear: true,
                initSelection: function (elem, callback) {
                    var val = $(elem).val();
                    callback({
                        id: val,
                        text: val,
                    });
                },
            });
        });
        $('.report-filter-multi-option').each(function() {
            var $filter = $(this),
                data = $filter.data();
console.log("endpoint=" + data.endpoint);
            $filter.parent().koApplyBindings({
                select_params: data.options,
                current_selection: ko.observableArray(data.selected),
            });

            if (!data.endpoint) {
                $filter.select2();
                return;
            }

            /*
             * If there's an endpoint, this is a select2 widget using a
             * remote endpoint for paginated, infinite scrolling options.
             * Check out EmwfOptionsView as an example
             * The endpoint should return json in this form:
             * {
             *     "total": 9935,
             *     "results": [
             *         {
             *             "text": "kingofthebritains (Arthur Pendragon)",
             *             "id": "a242ly1b392b270qp"
             *         },
             *         {
             *             "text": "thebrave (Sir Lancelot)",
             *             "id": "92b270qpa242ly1b3"
             *         }
             *      ]
             * }
             */
            $filter.select2({
                ajax: {
                    url: data.endpoint,
                    dataType: 'json',
                    data: function (term, page) {
                        return {
                            q: term,
                            page_limit: 10,
                            page: page,
                         };
                    },
                    results: function (data, page) {
                        var more = data.more || (page * 10) < data.total;
                        return {results: data.results, more: more};
                    }
                },
                initSelection: function (element, callback) {
                    var data = data.selected;
                    callback(data);
                },
                multiple: true,
                escapeMarkup: function (m) { return m; },
            }).select2('val', data.selected);
        });

        // Submission type (Raw Forms, Errors, & Duplicates)
        $('.report-filter-button-group').each(function() {
            hqImport("reports/js/filters/button_group").link(this);
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
            var model = hqImport("reports/js/filters/schedule_instance").scheduleInstanceFilterViewModel(data.initialValue, data.conditionalAlertChoices);
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
            var model = hqImport("reports/js/filters/phone_number").phoneNumberFilterViewModel(data.initialValue, data.groups);
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
