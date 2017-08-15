hqDefine("userreports/js/data_source_select", function() {
    $(function () {
        $("#report-builder-form").koApplyBindings({
            application: ko.observable(""),
            sourceType: ko.observable(""),
            sourcesMap: hqImport("hqwebapp/js/initial_page_data").get("sources_map"),
            labelMap: {'case': gettext('Case'), 'form': gettext('Form')},
        });
    });
});
