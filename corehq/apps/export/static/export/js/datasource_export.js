hqDefine("export/js/datasource_export",[
    'jquery',
    'knockout',
    'commcarehq',
], function ($, ko) {

    function datasourceExportViewModel() {
        var self = {};

        self.dataSource = ko.observable();
        self.haveDatasources = ko.computed(function () {
            return self.dataSource() !== undefined && self.dataSource().length;
        });

        return self;
    }

    $(function () {
        var datasourceExportModel = datasourceExportViewModel();
        $("#datasources_export_id").koApplyBindings(datasourceExportModel);
    });
});
