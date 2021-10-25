hqDefine('toggle_ui/js/flags', [
    'jquery',
    'knockout',
    'reports/js/config.dataTables.bootstrap',
    'hqwebapp/js/components.ko',    // select toggle widget
], function (
    $,
    ko,
    datatablesConfig
) {
    var dataTableElem = '.datatable';
    let buildViewModel = function () {
        let self = {};
        self.tagFilter = ko.observable(null);

        self.downloadFile = function () {
            var appliedFilter = self.tagFilter();
            if (appliedFilter === "all") {
                appliedFilter = '';
            }
            open('export_toggles?tag=' + appliedFilter);
        };

        return self;
    };

    let viewModel = buildViewModel();
    $.fn.dataTableExt.afnFiltering.push(
        function (oSettings, aData, iDataIndex) {
            if (viewModel.tagFilter() === 'all') {
                return true;
            }
            var tag = aData[0].replace(/\s+/g," ").replace(/<.*?>/g, "").replace(/^\d+ /, "");
            if (viewModel.tagFilter() === "Solutions" && tag.includes("Solutions")) {
                return true;
            }
            return tag === viewModel.tagFilter();
        }
    );
    $('#feature_flags').koApplyBindings(viewModel);
    var table = datatablesConfig.HQReportDataTables({
        dataTableElem: dataTableElem,
        showAllRowsOption: true,
        includeFilter: true,
    });
    table.render();

    viewModel.tagFilter.subscribe(function (value) {
        table.datatable.fnDraw();
    });
});
