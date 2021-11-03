hqDefine('userreports/js/data_source_from_app', function () {
    $(function () {
        let dataModel = hqImport("userreports/js/data_source_select_model");
        $("#data-source-config").koApplyBindings(dataModel);
    });
});
