hqDefine("succeed/js/patient_list", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    $(function() {
        var tableOptions = initialPageData.get('report_table_js_options');
        if (tableOptions && tableOptions.datatables) {
            var reportTablesOptions = {
                dataTableElem: '#report_table_' + initialPageData.get('slug'),
                defaultRows: tableOptions.default_rows || 10,
                startAtRowNum: tableOptions.start_at_row || 0,
                showAllRowsOption: tableOptions.show_all_rows,
                autoWidth: tableOptions.headers.auto_width,
                includeFilter: true,
                aaSorting: [[5, 'asc']],
            };
            if (reportTablesOptions.headers.render_aoColumns) {
                reportTablesOptions.aoColumns = tableOptions.headers.render_aoColumns;
            }
            if (tableOptions.headers.custom_sort) {
                reportTablesOptions.customSort = report_table.headers.custom_sort;
            }
            if (tableOptions.pagination.hide) {
                reportTablesOptions.show_pagination = false;
            }
            if (tableOptions.pagination.is_on) {
                reportTablesOptions = _.extend(reportTablesOptions, {
                    ajaxSource: tableOptions.pagination.source,
                    ajaxParams: tableOptions.pagination.params,
                };
            }
            if (tableOptions.bad_request_error_text) {
                reportTablesOptions.badRequestErrorText = "<span class='label label-danger'>Sorry!</span> " + tableOptions.bad_request_error_text;
            }
            if (tableOptions.left_col.is_fixed) {
                reportTablesOptions = _.extend(reportTablesOptions, {
                    fixColumns: true,
                    fixColsNumLeft: tableOptions.left_col.fixed.num,
                    fixColsWidth: tableOptions.left_col.fixed.width,
                });
            }
            var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables(reportTablesOptions);
            var standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
            if (typeof standardHQReport !== 'undefined') {
                standardHQReport.handleTabularReportCookies(reportTables);
            }
            reportTables.render();
        }

        $('.header-popover').popout({
            trigger: 'hover',
            placement: 'bottom'
        });
    });
});
