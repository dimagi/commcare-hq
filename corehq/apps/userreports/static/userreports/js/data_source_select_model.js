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
    let sourceData = [];
    if (self.sourceType() === 'case') {
        sourceData = self.sourcesMap['_all']?.[self.sourceType()];
    } else {
        sourceData = self.sourcesMap[self.application()]?.[self.sourceType()];
    }

    const unionResult = _.union(
        sourceData,
        self.sourcesMap[self.registrySlug()]?.[self.sourceType()],
    );

    return unionResult;
});

export default self;
