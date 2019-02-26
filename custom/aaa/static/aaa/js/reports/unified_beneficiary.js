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
    var tableDom = '<i<t><"row"<"col-md-2"><"col-md-8 center"<"table_pagination"p>><"col-md-2"<"table_info"l>>>>';

    var unifiedBeneficiary = function (options) {
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

        var views = {
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
                data.push(reportListView.listView(row, self.postData))
            });
            return data;
        };

        self.updateTable = function () {
            if (selectedType !== null) {
                self.dt.clear().draw().destroy();
                $('#datatable').empty();
            }
            selectedType = self.postData.selectedBeneficiaryType();
            reportListView = views[selectedType];

            self.dt = $('#datatable').DataTable({
                dom: tableDom,
                columns: reportListView.config().columns,
                serverSide: true,
                ajax: function (data, callback, settings) {
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
                                data: rows
                            })
                        });
                    }
                }
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
