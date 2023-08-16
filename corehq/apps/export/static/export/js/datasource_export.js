hqDefine("export/js/datasource_export",[
    'jquery',
    'knockout',
], function ($, ko) {

    function datasourceExportViewModel() {
        'use strict';
        var self = {};

        self.dataSource = ko.observable();
        self.haveDatasources = ko.computed(function () {
            if (self.dataSource() === undefined) { return false; }
            return self.dataSource().length > 0;
        });
        self.updateExportButton = ko.computed(function () {
            $("#datasources_export_submit_button_id").prop('disabled', !self.haveDatasources());
        });

        return self;
    }

    $(function () {
        var datasourceExportModel = datasourceExportViewModel();
        $("#datasources_export_id").koApplyBindings(datasourceExportModel);
    });
});
