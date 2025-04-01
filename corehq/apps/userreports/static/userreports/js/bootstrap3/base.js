hqDefine('userreports/js/bootstrap3/base', [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'reports_core/js/charts',
    'reports_core/js/bootstrap3/maps',
    'reports/js/bootstrap3/datatables_config',
    'reports/js/charts/main',
    'reports/js/filters/bootstrap3/main',
], function (
    $,
    _,
    initialPageData,
    charts,
    maps,
    dataTablesConfig,
    chartsMain,
    filtersMain,
) {
    var main = function (options) {
        var o = _.extend({
            chartSpecs: initialPageData.get('charts'),
            isReportBuilderReport: initialPageData.get('created_by_builder'),
            htmlIDSuffix: initialPageData.get('html_id_suffix'),
            mapSpec: initialPageData.get('map_config'),
            mapboxAccessToken: initialPageData.get('MAPBOX_ACCESS_TOKEN'),
            reportSlug: initialPageData.get('report_slug'),
            tableDefaultRows: initialPageData.get('table_default_rows'),
            tableStartAtRow: initialPageData.get('table_start_at_row'),
            tableShowAllRows: initialPageData.get('table_show_all_rows'),
            renderAoColumns: initialPageData.get('render_aoColumns'),
            headerAutoWidth: initialPageData.get('header_auto_width'),
            customSort: initialPageData.get('custom_sort'),
            url: initialPageData.get('url'),
            ajaxMethod: initialPageData.get('ajax_method'),
            leftColIsFixed: initialPageData.get('left_col_is_fixed'),
            leftColFixedNum: initialPageData.get('left_col_fixed_num'),
            leftColFixedWidth: initialPageData.get('left_col_fixed_width'),
        }, options);

        var updateCharts = function (data) {
            if (o.chartSpecs !== null && o.chartSpecs.length > 0) {
                if (data.iTotalRecords > 25 && o.isReportBuilderReport) {
                    $("#chart-warning" + o.htmlIDSuffix).removeClass("hide");
                    charts.clear($("#chart-container" + o.htmlIDSuffix));
                } else {
                    $("#chart-warning" + o.htmlIDSuffix).addClass("hide");
                    charts.render(chartSpecs, data.aaData, $("#chart-container" + o.htmlIDSuffix));
                }
            }
        };

        var updateMap = function (data) {
            if (o.mapSpec) {
                o.mapSpec.mapboxAccessToken = o.mapboxAccessToken;
                maps.render(o.mapSpec, data.aaData, $("#map-container" + o.htmlIDSuffix));
            }
        };

        var paginationNotice = function (data) {
            if (o.mapSpec) {  // Only show warning for map reports
                if (data.aaData !== undefined && data.iTotalRecords !== undefined) {
                    if (data.aaData.length < data.iTotalRecords) {
                        $('#info-message' + o.htmlIDSuffix).html(
                            gettext('Showing the current page of data. Switch pages to see more data.'),
                        );
                        $('#report-info' + o.htmlIDSuffix).removeClass('hide');
                    } else {
                        $('#report-info' + o.htmlIDSuffix).addClass('hide');
                    }
                }
            }
        };

        var errorCallback = function (jqXHR, textStatus, errorThrown) {
            $('#error-message' + o.htmlIDSuffix).html(errorThrown);
            $('#report-error' + o.htmlIDSuffix).removeClass('hide');
        };

        var successCallback = function (data) {
            if (data.error || data.error_message) {
                const message = data.error || data.error_message;
                $('#error-message' + o.htmlIDSuffix).html(message);
                $('#report-error' + o.htmlIDSuffix).removeClass('hide');
            } else {
                $('#report-error' + o.htmlIDSuffix).addClass('hide');
            }
            if (data.warning) {
                $('#warning-message' + o.htmlIDSuffix).html(data.warning);
                $('#report-warning' + o.htmlIDSuffix).removeClass('hide');
            } else {
                $('#report-warning' + o.htmlIDSuffix).addClass('hide');
            }
        };

        var reportTables = dataTablesConfig.HQReportDataTables({
            dataTableElem: '#report_table_' + o.reportSlug + o.htmlIDSuffix,
            defaultRows: o.tableDefaultRows,
            startAtRowNum: o.tableStartAtRow,
            showAllRowsOption: o.tableShowAllRows,
            aaSorting: [],
            aoColumns: o.renderAoColumns,
            autoWidth: o.headerAutoWidth,
            customSort: o.customSort,
            ajaxSource: getReportUrl(),
            ajaxMethod: o.ajaxMethod,
            ajaxParams: function () {
                return $('#paramSelectorForm' + o.htmlIDSuffix).serializeArray();
            },
            fixColumns: o.leftColIsFixed,
            fixColsNumLeft: o.leftColFixedNum,
            fixColsWidth: o.leftColFixedWidth,
            successCallbacks: [successCallback, updateCharts, updateMap, paginationNotice],
            errorCallbacks: [errorCallback],
        });
        $('#paramSelectorForm' + o.htmlIDSuffix).submit(function (event) {
            $('#reportHint' + o.htmlIDSuffix).remove();
            $('#reportContent' + o.htmlIDSuffix).removeClass('hide');
            event.preventDefault();
            reportTables.render();
        });
        // after we've registered the event that prevents the default form submission
        // we can enable the submit button
        $("#apply-filters" + o.htmlIDSuffix).prop('disabled', false);
    };

    $(function () {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
            container: 'body',
        });
    });

    // filter init
    $(function () {
        filtersMain.init();
        chartsMain.init();
    });

    return {
        main: main,
    };
});
