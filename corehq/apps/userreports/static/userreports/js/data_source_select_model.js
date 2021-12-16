hqDefine("userreports/js/data_source_select_model", function () {
    return {
        application: ko.observable(""),
        sourceType: ko.observable(""),
        sourcesMap: hqImport("hqwebapp/js/initial_page_data").get("sources_map"),
        dropdownMap: hqImport("hqwebapp/js/initial_page_data").get("dropdown_map"),
        labelMap: {
            'case': gettext('Case'),
            'form': gettext('Form'),
            'data_source': gettext('Data Source'),
        },
        sourceId: ko.observable(""),
        registrySlug: ko.observable(""),
        isDataFromOneProject: ko.observable(""),
        isDataFromManyProjects: ko.observable(""),
    };
});
