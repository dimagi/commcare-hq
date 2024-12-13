hqDefine("inddex/js/main", function () {
    // TODO: test: don't think this runs when the report data changes
    $(function () {
        $("[data-report-table]").each(function (table) {
            const $table = $(table),
                reportTable = $table.data("report-table");

            if (!reportTable || !reportTable.datatables) {
                return;
            }

            let options = {
                dataTableElem: '#report_table_' + reportTable.slug,
                defaultRows: reportTable.default_rows || 10,
                startAtRowNum: reportTable.default_rows || 10,
                showAllRowsOption: reportTable.show_all_rows,
                loadingTemplateSelector: '#js-template-loading-report',
                defaultSort: true,
                autoWidth: reportTable.headers.auto_width,
                fixColumns: true,
                fixColsNumLeft: 1,
                fixColsWidth: 130,
            };
            if (reportTable.headers.render_aoColumns) {
                options.aoColumns = reportTable.headers.render_aoColumns;
            }
            if (reportTable.headers.custom_sort) {
                options.customSort = reportTable.headers.custom_sort;
            }
            if (reportTable.pagination.is_on) {
                options.ajaxSource = reportTable.pagination.source;
                options.ajaxParams = reportTable.pagination.params;
            }
            if (reportTable.bad_request_error_text) {
                options.badRequestErrorText = "<span class='label label-danger'>Sorry!</span> " + reportTable.bad_request_error_text;
            }

            var reportTables = hqImport("reports/js/bootstrap3/datatables_config").HQReportDataTables(options);
            var standardHQReport = hqImport("reports/js/bootstrap3/standard_hq_report").getStandardHQReport();
            if (typeof standardHQReport !== 'undefined') {
                standardHQReport.handleTabularReportCookies(reportTables);
            }
            reportTables.render();
        });
    });
});
