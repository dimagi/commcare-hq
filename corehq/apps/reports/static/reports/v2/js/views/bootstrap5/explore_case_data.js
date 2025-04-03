hqDefine('reports/v2/js/views/bootstrap5/explore_case_data', [
    'jquery',
    'knockout',
    'underscore',
    'reports/v2/js/context',
    'reports/v2/js/bootstrap5/datagrid',
    'hqwebapp/js/components/bootstrap5/feedback',
], function (
    $,
    ko,
    _,
    context,
    datagrid,
) {
    var view = {};

    view.config = context.getReportConfig();

    view.datagridController = datagrid.datagridController({
        dataModel: datagrid.dataModels.scrollingDataModel(view.config.endpoint.datagrid),
        initialColumns: context.getColumns(),
        columnEndpoint: view.config.endpoint.case_properties,
        columnFilters: context.getColumnFilters(),
        reportFilters: context.getReportFilters(),
        hideColumnFilterCondition: function (column) {
            return column.name() === '@case_type';
        },
        noDeleteColumnCondition: function (column) {
            return column.name() === 'case_name';
        },
        unsortableColumnNames: context.getUnsortableColumnNames(),
    });

    view.datagridController.init();

    $(function () {
        $('#report-datagrid').koApplyBindings(view.datagridController);
    });

    return view;
});
