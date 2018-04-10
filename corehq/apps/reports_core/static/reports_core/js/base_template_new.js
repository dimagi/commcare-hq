hqDefine('reports_core/js/base_template_new', function() {
var initialPageData = hqImport('hqwebapp/js/initial_page_data');
        var base_url = "initialPageData.get('url')";
        function get_report_url() {
            return base_url;
        }
    $(function() {
        var charts = hqImport('reports_core/js/charts');
        var chartSpecs = initialPageData.get('report.spec.charts|JSON');
        var updateCharts = function (data) {
            if (chartSpecs !== null && chartSpecs.length > 0) {
                var isReportBuilderReport = initialPageData.get('report.spec.report_meta.created_by_builder|JSON');
                if (data.iTotalRecords > 25 && isReportBuilderReport) {
                    $("#chart-warning").removeClass("hide");
                    charts.clear($("#chart-container"));
                } else {
                    $("#chart-warning").addClass("hide");
                    charts.render(chartSpecs, data.aaData, $("#chart-container"));
                }
            }
        };

        var mapSpec = initialPageData.get('report.spec.map_config|JSON');
        var updateMap = function (data) {
            if (mapSpec) {
                mapSpec.mapboxAccessToken = 'initialPageData.get('MAPBOX_ACCESS_TOKEN')';
                var render_map = hqImport('reports_core/js/maps').render;
                render_map(mapSpec, data.aaData, $("#map-container"));
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

        var successCallback = function(data) {
            if(data.error) {
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

        var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables({
            dataTableElem: '#report_table_initialPageData.get('report.slug')',
            defaultRows: initialPageData.get('report_table.default_rows|default:10'),
            startAtRowNum: initialPageData.get('report_table.start_at_row|default:0'),
            showAllRowsOption: initialPageData.get('report_table.show_all_rows|JSON'),
            aaSorting: [],
            initialPageData.get('if headers.render_aoColumns')aoColumns: {{ headers.render_aoColumns|JSON }},{% endif %}
            autoWidth: initialPageData.get('headers.auto_width|JSON'),
            initialPageData.get('if headers.custom_sort')customSort: {{ headers.custom_sort|JSON }},{% endif %}

            ajaxSource: 'initialPageData.get('url')',
            ajaxMethod: 'initialPageData.get('method')',
            ajaxParams: function() {
                return $('#paramSelectorForm').serializeArray();
            },
            initialPageData.get('if report_table.left_col.is_fixed')
                fixColumns: true,
                fixColsNumLeft: initialPageData.get('report_table.left_col.fixed.num'),
                fixColsWidth: initialPageData.get('report_table.left_col.fixed.width'),
            initialPageData.get('endif')
            successCallbacks: [successCallback, updateCharts, updateMap, paginationNotice],
            errorCallbacks: [errorCallback]
        });
        $('#paramSelectorForm').submit(function(event) {
            $('#reportHint').remove();
            $('#reportContent').removeClass('hide');
            event.preventDefault();
            reportTables.render();
        });
        // after we've registered the event that prevents the default form submission
        // we can enable the submit button
        $("#apply-filters").prop('disabled', false);

        $(function() {
            $('.header-popover').popover({
                trigger: 'hover',
                placement: 'bottom',
                container: 'body'
            });
        });

    });

    $(function () {
        // add any filter javascript dependencies
        initialPageData.get('for filter in report.filters')
            initialPageData.get('if filter.javascript_template')
                initialPageData.get('include filter.javascript_template with filter=filter context_=filter_context|dict_lookup:filter.css_id')
            initialPageData.get('endif')
        initialPageData.get('endfor')
    });
});
