import 'commcarehq';

import $ from 'jquery';
import _ from 'underscore';
import {Popover} from 'bootstrap5';

import initialPageData from 'hqwebapp/js/initial_page_data';
import datatablesConfig from 'reports/js/bootstrap5/datatables_config';
import standardHQReportModule from 'reports/js/bootstrap5/standard_hq_report';

import 'reports/js/datepicker';

import 'data_interfaces/js/bootstrap5/case_management';
import 'data_interfaces/js/archive_forms';
import 'reports/js/inspect_data';
import 'reports/js/bootstrap5/project_health_dashboard';
import 'reports/js/bootstrap5/aggregate_user_status';
import 'reports/js/bootstrap5/application_status';
import 'reports/js/user_history';
import 'reports/js/case_activity';


function renderPage(slug, tableOptions) {
    if (tableOptions && tableOptions.datatables) {
        var tableConfig = tableOptions,
            options = {
                dataTableElem: '#report_table_' + slug,
                forcePageSize: tableConfig.force_page_size,
                defaultRows: tableConfig.default_rows,
                startAtRowNum: tableConfig.start_at_row,
                showAllRowsOption: tableConfig.show_all_rows,
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
            options.badRequestErrorText = "<span class='badge text-bg-danger'>" + gettext("Sorry!") + "</span>" + tableConfig.bad_request_error_text;
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

    const tableHeadersWithInfo = document.getElementsByClassName('header-popover');
    Array.from(tableHeadersWithInfo).forEach((elem) => {
        new Popover(elem, {
            title: elem.dataset.title,
            content: elem.dataset.content,
            trigger: 'hover',
            placement: 'bottom',
            container: 'body',
        });
    });
}

// Handle async reports
$(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
    if (!data || !data.slug) {
        // This file is imported by inddex/main, which then gets this event handler, which it doesn't need,
        // and which errors sometimes (presumably because there are ajax requests happening that aren't the
        // same as what this handler expects). Checking for data.slug is pretty innocuous and fixes the issue.
        return;
    }
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

export default {
    renderPage: renderPage,
};
