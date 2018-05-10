hqDefine("reports/js/async_tabular", function() {
    function renderPage(data) {
        if (data.report_table && data.report_table.datatables) {
            var options = {
                dataTableElem: '#report_table_' + data.slug,
                defaultRows: data.report_table.default_rows,
                startAtRowNum: data.report_table.start_at_row,
                showAllRowsOption: data.report_table.show_all_rows,
                loadingTemplateSelector: '#js-template-loading-report',
                autoWidth: data.report_table.headers.auto_width,
            };
            if (!data.report_table.sortable) {
                options.defaultSort = false;
            }
            if (data.report_table.headers.render_aoColumns) {
                options.aoColumns = data.report_table.headers.render_aoColumns;
            }
            if (data.report_table.headers.custom_sort) {
                options.customSort = data.report_table.headers.custom_sort;
            }
            if (data.report_table.pagination.hide) {
                options.show_pagination = false;
            }
            if (data.report_table.pagination.is_on) {
                _.extend(options, {
                    ajaxSource: data.report_table.pagination.source,
                    ajaxParams: data.report_table.pagination.params,
                });
            }
            if (data.report_table.bad_request_error_text) {
                options.badRequestErrorText = "<span class='label label-important'>" + gettext("Sorry!") + "</span>" + data.report_table.bad_request_error_text;
            }
            if (data.report_table.left_col.is_fixed) {
                _.extend(options, {
                    fixColumns: true,
                    fixColsNumLeft: data.report_table.left_col.fixed.num,
                    fixColsWidth: data.report_table.left_col.fixed.width,
                });
            }
            var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables(options);
            var standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
            if (typeof standardHQReport !== 'undefined') {
                standardHQReport.handleTabularReportCookies(reportTables);
            }
            reportTables.render();
        }
    }

    $(document).on('ajaxSuccess', function(e, xhr, ajaxOptions, data) {
        var jsOptions = hqImport("hqwebapp/js/initial_page_data").get("js_options");
        if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
            return;
        }
        renderPage(data);
    });
});
