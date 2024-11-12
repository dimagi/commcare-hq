hqDefine('reports/v2/js/views/bootstrap3/explore_case_data', [
    'jquery',
    'knockout',
    'underscore',
    'reports/v2/js/context',
    'reports/v2/js/bootstrap3/datagrid',
    'hqwebapp/js/components/bootstrap3/feedback',
    'commcarehq',
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
