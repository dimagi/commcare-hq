hqDefine('userreports/js/data_source_from_app', function() {
    $(function () {
        $("#data-source-config").koApplyBindings({
            application: ko.observable(""),
            sourceType: ko.observable(""),
            sourcesMap: hqImport("hqwebapp/js/initial_page_data").get("sources_map"),
        });
    });
});
