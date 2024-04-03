hqDefine("reports/js/bootstrap5/tabular", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap5/config.dataTables.bootstrap',
    'reports/js/bootstrap5/standard_hq_report',
], function (
    $,
    _,
    initialPageData,
    datatablesConfig,
    standardHQReportModule
) {
    function renderPage(slug, tableOptions) {
        if (tableOptions && tableOptions.datatables) {
            var tableConfig = tableOptions,
                options = {
                    dataTableElem: '#report_table_' + slug,
                    forcePageSize: tableConfig.force_page_size,
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
            var reportTables = datatablesConfig.HQReportDataTables(options);
            var standardHQReport = standardHQReportModule.getStandardHQReport();
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

    // Handle async reports
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
        var jsOptions = initialPageData.get("js_options");
        if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
            return;
        }
        renderPage(data.slug, data.report_table_js_options);
    });

    // Handle sync reports
    $(function () {
        if (initialPageData.get("report_table_js_options")) {
            renderPage(initialPageData.get("js_options").slug, initialPageData.get("report_table_js_options"));
        }
    });
});
