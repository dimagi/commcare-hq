hqDefine("intrahealth/js/multi_report_table", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    $(document).on("ajaxComplete", function (e, xhr, options) {
        var fragment = "async/",
            pageUrl = window.location.href.split('?')[0],
            ajaxUrl = options.url.split('?')[0];
        if (ajaxUrl.indexOf(fragment) === -1 || !pageUrl.endsWith(ajaxUrl.replace(fragment, ''))) {
            return;
        }
        var tableOptions = initialPageData.get('report_table_js_options');
        if (tableOptions && tableOptions.datatables) {
            var reportTablesOptions = {
                dataTableElem: '#report_table_' + tableOptions,
                defaultRows: tableOptions.default_rows || 10,
                startAtRowNum: tableOptions.start_at_row || 0,
                showAllRowsOption: tableOptions.show_all_rows,
                loadingTemplateSelector: '#js-template-loading-report',
                autoWidth: tableOptions.headers.auto_width,
                defaultSort: true,
                fixColumns: true,
                fixColsNumLeft: 1,
                fixColsWidth: 130,
            };
            if (reportTablesOptions.headers.render_aoColumns) {
                reportTablesOptions.aoColumns = tableOptions.headers.render_aoColumns;
            }
            if (tableOptions.headers.custom_sort) {
                reportTablesOptions.customSort = tableOptions.headers.custom_sort;
            }
            if (tableOptions.bad_request_error_text) {
                reportTablesOptions.badRequestErrorText = "<span class='label label-danger'>Sorry!</span> " + tableOptions.bad_request_error_text;
            }
            if (tableOptions.pagination.is_on) {
                reportTablesOptions.ajaxSource = tableOptions.pagination.source;
                reportTablesOptions.ajaxParams = tableOptions.pagination.params;
            }
            var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables(reportTablesOptions);
            var standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
            if (typeof standardHQReport !== 'undefined') {
                standardHQReport.handleTabularReportCookies(reportTables);
            }
            reportTables.render();
        }
    });
});
