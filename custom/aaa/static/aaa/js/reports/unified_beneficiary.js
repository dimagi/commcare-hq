hqDefine("aaa/js/reports/unified_beneficiary", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/utils/reach_utils',
    'aaa/js/models/eligible_couple',
    'aaa/js/models/child',
    'aaa/js/models/pregnant_women',
], function (
    $,
    ko,
    _,
    initialPageData,
    reachUtils,
    eligibleCoupleModel,
    childModel,
    pregnantWomenModel
) {
    var tableDom = '<i<t><"row"<"col-md-2" B><"col-md-8 center"<"table_pagination"p>><"col-md-2"<"table_info"l>>>>';

    var unifiedBeneficiary = function () {
        var self = {};
        self.sections = ko.observableArray();
        self.title = 'Unified Beneficiary';
        self.slug = 'unified_beneficiary';
        self.postData = reachUtils.postData({});
        self.localStorage = reachUtils.localStorage();
        self.localStorage.showModal(true);
        self.reachUtils = reachUtils.reachUtils();

        self.filters = {
            'month-year-filter': {},
            'location-filter': {},
            'beneficiary-type-filter': {},
        };

        self.dt = null;

        self.views = {
            'eligible_couple': eligibleCoupleModel,
            'pregnant_women': pregnantWomenModel,
            'child': childModel,
        };

        var selectedType = null;
        var reportListView = null;

        self.updateRows = function (rows) {
            var data = [];
            self.dt.clear();
            _.forEach(rows, function (row) {
                data.push(reportListView.listView(row, self.postData));
            });
            return data;
        };

        self.task_id = null;
        self.statusCheck = null;
        self.exportButton = null;
        self.exportUrl = null;

        self.checkTaskStatus = function () {
            var checkStatusUrl = initialPageData.reverse('aaa_check_task_status');
            checkStatusUrl = checkStatusUrl.replace('task_id', self.task_id);
            $.get(checkStatusUrl, function (response) {
                if (response.task_ready) {
                    clearInterval(self.statusCheck);
                    var exportUrl = initialPageData.reverse('aaa_download_file');
                    self.exportUrl = exportUrl.replace('file_id', response.task_result);
                    $(self.exportButton).text('Download');
                }
            });
        };

        self.updateTable = function () {
            if (selectedType !== null) {
                self.dt.clear().draw().destroy();
                $('#datatable').empty();
            }
            selectedType = self.postData.selectedBeneficiaryType();
            reportListView = self.views[selectedType];

            self.dt = $('#datatable').DataTable({
                dom: tableDom,
                columns: reportListView.config().columns,
                serverSide: true,
                buttons: [{
                    text: 'Export List',
                    action: function (e, dt, node) {
                        if (self.task_id === null) {
                            self.exportButton = node;
                            $(self.exportButton).text('Please wait!');
                            $.post(initialPageData.reverse('aaa_export_data'), self.postData, function (response) {
                                self.task_id = response.task_id;
                                self.statusCheck = setInterval(self.checkTaskStatus, 5 * 1000);
                            });
                        } else {
                            $(self.exportButton).text('Export List');
                            self.task_id = null;
                            window.open(self.exportUrl);
                        }
                    },
                }],
                ajax: function (data, callback) {
                    /* TODO: check why the ajax function is calling when the table is removed.

                       For now, we compare selected BeneficiaryType with this in
                       ajax function context because without this we get the js error
                       that the 'datatables' can't fill the old table.

                       This is called for old table even when we run destroy() function which
                       should totally remove old definition
                    */
                    if (self.postData.selectedBeneficiaryType() === selectedType) {
                        var params = {
                            draw: data.draw,
                            length: data.length,
                            start: data.start,
                            sortColumn: data.columns[data.order[0].column].name,
                            sortColumnDir: data.order[0].dir,
                        };
                        $.post(initialPageData.reverse('unified_beneficiary_api'), Object.assign(params, self.postData), function (response) {
                            var rows = self.updateRows(response.rows);
                            callback({
                                draw: response.draw,
                                recordsTotal: response.recordsTotal,
                                recordsFiltered: response.recordsFiltered,
                                data: rows,
                            });
                        });
                    }
                },
            });
        };

        self.callback = function () {
            self.updateTable();
        };

        self.isActive = function (slug) {
            return self.slug === slug;
        };

        return self;
    };

    $(function () {
        var model = unifiedBeneficiary();
        $('#aaa-dashboard').koApplyBindings(model);
    });

    return {
        unifiedBeneficiary: unifiedBeneficiary,
    };
});
