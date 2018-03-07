hqDefine('toggle_ui/js/flags', [
    'jquery',
    'knockout',
    'reports/js/config.dataTables.bootstrap',
], function (
    $,
    ko,
    datatablesConfig
) {
    var dataTableElem = '.datatable';
    var viewModel = {
        tagFilter: ko.observable(null),
    };
    $.fn.dataTableExt.afnFiltering.push(
        function( oSettings, aData, iDataIndex ) {
            if (viewModel.tagFilter() === null) {
                return true;
            }
            var tag = aData[0].replace(/\n/g," ").replace( /<.*?>/g, "" );
            return tag === viewModel.tagFilter();
        }
    );
    $('#table-filters').koApplyBindings(viewModel);
    var table = datatablesConfig.HQReportDataTables({
        dataTableElem: dataTableElem,
        showAllRowsOption: true,
        includeFilter: true,
    });
    table.render();

    viewModel.tagFilter.subscribe(function(value){
        table.datatable.fnDraw();
    });
});
