hqDefine('reports_core/js/base_template_new', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var baseUrl = initialPageData.get('url');
    function getReportUrl() {
        return baseUrl;
    }
    $(function () {
        var charts = hqImport('reports_core/js/charts');
        var chartSpecs = initialPageData.get('charts');
        var updateCharts = function (data) {
            if (chartSpecs !== null && chartSpecs.length > 0) {
                var isReportBuilderReport = initialPageData.get('created_by_builder');
                if (data.iTotalRecords > 25 && isReportBuilderReport) {
                    $("#chart-warning").removeClass("hide");
                    charts.clear($("#chart-container"));
                } else {
                    $("#chart-warning").addClass("hide");
                    charts.render(chartSpecs, data.aaData, $("#chart-container"));
                }
            }
        };

        var mapSpec = initialPageData.get('map_config');
        var updateMap = function (data) {
            if (mapSpec) {
                mapSpec.mapboxAccessToken = initialPageData.get('MAPBOX_ACCESS_TOKEN');
                var renderMap = hqImport('reports_core/js/maps').render;
                renderMap(mapSpec, data.aaData, $("#map-container"));
            }
        };

        var paginationNotice = function (data) {
            if (mapSpec) {  // Only show warning for map reports
                if (data.aaData !== undefined && data.iTotalRecords !== undefined) {
                    if (data.aaData.length < data.iTotalRecords) {
                        $('#info-message').html(
                            gettext('Showing the current page of data. Switch pages to see more data.')
                        );
                        $('#report-info').removeClass('hide');
                    } else {
                        $('#report-info').addClass('hide');
                    }
                }
            }
        };

        var errorCallback = function (jqXHR, textStatus, errorThrown) {
            $('#error-message').html(errorThrown);
            $('#report-error').removeClass('hide');
        };

        var successCallback = function (data) {
            if (data.error) {
                $('#error-message').html(data.error);
                $('#report-error').removeClass('hide');
            } else {
                $('#report-error').addClass('hide');
            }
            if (data.warning) {
                $('#warning-message').html(data.warning);
                $('#report-warning').removeClass('hide');
            } else {
                $('#report-warning').addClass('hide');
            }
        };

        var reportTables = hqImport("reports/js/bootstrap3/config.dataTables.bootstrap").HQReportDataTables({
            dataTableElem: '#report_table_' + initialPageData.get('report_slug'),
            defaultRows: initialPageData.get('table_default_rows'),
            startAtRowNum: initialPageData.get('table_start_at_row'),
            showAllRowsOption: initialPageData.get('table_show_all_rows'),
            aaSorting: [],
            aoColumns: initialPageData.get('render_aoColumns'),
            autoWidth: initialPageData.get('header_auto_width'),
            customSort: initialPageData.get('custom_sort'),
            ajaxSource: getReportUrl(),
            ajaxMethod: initialPageData.get('ajax_method'),
            ajaxParams: function () {
                return $('#paramSelectorForm').serializeArray();
            },
            fixColumns: initialPageData.get('left_col_is_fixed'),
            fixColsNumLeft: initialPageData.get('left_col_fixed_num'),
            fixColsWidth: initialPageData.get('left_col_fixed_width'),
            successCallbacks: [successCallback, updateCharts, updateMap, paginationNotice],
            errorCallbacks: [errorCallback],
        });
        $('#paramSelectorForm').submit(function (event) {
            $('#reportHint').remove();
            $('#reportContent').removeClass('hide');
            event.preventDefault();
            reportTables.render();
        });
        // after we've registered the event that prevents the default form submission
        // we can enable the submit button
        $("#apply-filters").prop('disabled', false);

        $(function () {
            $('.header-popover').popover({
                trigger: 'hover',
                placement: 'bottom',
                container: 'body',
            });
        });

        // filter init
        $(function () {
            hqImport("reports/js/filters/bootstrap3/main").init();
            hqImport("reports/js/charts/main").init();
        });
    });
});
