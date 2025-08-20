import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

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

export default self;
