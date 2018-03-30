hqDefine('userreports/js/data_source_debugger', function() {
    $(function () {
        var DataSourceModel = hqImport('userreports/js/data_source_evaluator').DataSourceModel;
        var submitUrl = hqImport("hqwebapp/js/initial_page_data").reverse("data_source_evaluator");

        $("#data-source-debugger").koApplyBindings(new DataSourceModel(submitUrl));
    });
});
