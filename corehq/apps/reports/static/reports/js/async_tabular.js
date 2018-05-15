hqDefine("reports/js/async_tabular", function() {
    function renderPage(data) {
        if (data.report_table_js_options && data.report_table_js_options.datatables) {
            var tableConfig = data.report_table_js_options,
                options = {
                    dataTableElem: '#report_table_' + data.slug,
                    defaultRows: tableConfig.default_rows,
                    startAtRowNum: tableConfig.start_at_row,
                    showAllRowsOption: tableConfig.show_all_rows,
                    loadingTemplateSelector: '#js-template-loading-report',
                    autoWidth: tableConfig.headers.auto_width,
                };
            if (!tableConfig.sortable) {
                options.defaultSort = false;
            }
            if (tableConfig.headers.render_aoColumns) {
                options.aoColumns = tableConfig.headers.render_aoColumns;
            }
            if (tableConfig.headers.custom_sort) {
                options.customSort = tableConfig.headers.custom_sort;
            }
            if (tableConfig.pagination.hide) {
                options.show_pagination = false;
            }
            if (tableConfig.pagination.is_on) {
                _.extend(options, {
                    ajaxSource: tableConfig.pagination.source,
                    ajaxParams: tableConfig.pagination.params,
                });
            }
            if (tableConfig.bad_request_error_text) {
                options.badRequestErrorText = "<span class='label label-important'>" + gettext("Sorry!") + "</span>" + tableConfig.bad_request_error_text;
            }
            if (tableConfig.left_col.is_fixed) {
                _.extend(options, {
                    fixColumns: true,
                    fixColsNumLeft: tableConfig.left_col.fixed.num,
                    fixColsWidth: tableConfig.left_col.fixed.width,
                });
            }
            var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables(options);
            var standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
            if (typeof standardHQReport !== 'undefined') {
                standardHQReport.handleTabularReportCookies(reportTables);
            }
            reportTables.render();
        }

        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
            container: 'body',
        });
    }

    $(document).on('ajaxSuccess', function(e, xhr, ajaxOptions, data) {
        var jsOptions = hqImport("hqwebapp/js/initial_page_data").get("js_options");
        if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
            return;
        }
        renderPage(data);
    });
});
