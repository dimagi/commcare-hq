hqDefine("userreports/js/data_source_select.js", function() {
    $(function () {
        $("#report-builder-form").koApplyBindings({
            application: ko.observable(""),
            sourceType: ko.observable(""),
            sourcesMap: hqImport("hqwebapp/js/initial_page_data.js").get("sources_map"),
            labelMap: {'case': gettext('Case'), 'form': gettext('Form')},
        });
    });
});
