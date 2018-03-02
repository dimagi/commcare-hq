hqDefine('userreports/js/reportbuilder/configure_report', function() {

    var ReportBuilder = {
      Constants: hqImport("userreports/js/constants"),
    };

    $(document).ready(function() {
        var reportConfig = new reportBuilder.ReportConfig({
            "columnOptions": {{ column_options|JSON }},
            "initialColumns": {{ initial_columns|JSON }},
            "app": {{ application|JSON }},
            "sourceId": {{ source_id|JSON }},
            "sourceType": "{{ source_type }}",
            "reportPreviewUrl": "{{ report_preview_url }}",
            "previewDatasourceId": "{{ preview_datasource_id }}",
            "existingReport": {% if existing_report %}{{ existing_report.get_id|JSON }}{% else %}null{% endif %},
            "existingReportType": {{ existing_report_type|JSON }},
            "reportTitle": "{{ report_title|escapejs }}",
            "reportDescription": {% if report_description %}"{{ report_description|escapejs }}"{% else %}null{% endif %},
            "dataSourceProperties": {{ data_source_properties|JSON }},
            "initialDefaultFilters": {{ initial_default_filters|JSON }},
            "initialUserFilters": {{ initial_user_filters|JSON }},
            "initialLocation": {{ initial_location|JSON }},
            "initialChartType": {{ initial_chart_type|JSON }},
            "mapboxAccessToken": {{ MAPBOX_ACCESS_TOKEN|JSON }},
            "dateRangeOptions": {{ date_range_options|JSON }},
            // In previewMode, report can't be saved.
            "previewMode":
              {# equivalent to: not has_report_builder_access or (at_report_limit and not existing_report) #}
              {% if not has_report_builder_access or at_report_limit and not existing_report %}
                true
              {% else %}
                false
              {% endif %}
            ,

        });
        $("#reportConfig").koApplyBindings(reportConfig);
        window._bindingsApplied = true;
    });
});
