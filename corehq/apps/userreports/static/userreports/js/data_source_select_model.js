hqDefine("userreports/js/data_source_select_model", [
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    ko,
    _,
    initialPageData,
) {
    var self = {
        application: ko.observable(""),
        sourceType: ko.observable(""),
        sourcesMap: initialPageData.get("sources_map"),
        dropdownMap: initialPageData.get("dropdown_map"),
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

    self.sourceOptions = ko.computed(function () {
        return _.union(
            self.sourcesMap[self.application()]?.[self.sourceType()],
            self.sourcesMap[self.registrySlug()]?.[self.sourceType()],
        );
    });

    return self;
});
