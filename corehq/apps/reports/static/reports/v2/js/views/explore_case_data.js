hqDefine('reports/v2/js/views/explore_case_data', [
    'jquery',
    'knockout',
    'underscore',
    'reports/v2/js/context',
    'reports/v2/js/datagrid',
], function (
    $,
    ko,
    _,
    context,
    datagrid
) {
    'use strict';
    var view = {};

    view.config = context.getReportConfig();

    view.datagridController = datagrid.datagridController({
        dataModel: datagrid.dataModels.scrollingDataModel(view.config.endpoint.datagrid),
        initialColumns: context.getColumns(),
        columnEndpoint: view.config.endpoint.case_properties,
        columnFilters: context.getColumnFilters(),
        reportFilters: context.getReportFilters(),
    });

    view.datagridController.init();

    $(function () {
        $('#report-datagrid').koApplyBindings(view.datagridController);
    });

    return view;
});
