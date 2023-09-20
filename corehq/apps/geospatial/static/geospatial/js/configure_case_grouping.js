hqDefine("geospatial/js/configure_case_grouping",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var caseGroupingModel = function (configData) {
        'use strict';
        var self = {};

        const targetGroupingName = configData.get('target_grouping_name');
        const minMaxGroupingName = configData.get('min_max_grouping_name');

        self.selectedGroupMethod = ko.observable();

        self.isTargetGrouping = ko.computed(function () {
            return self.selectedGroupMethod() === targetGroupingName;
        });
        self.isMinMaxGrouping = ko.computed(function () {
            return self.selectedGroupMethod() === minMaxGroupingName;
        });

        return self;
    };

    $(function () {
        const configOptions = caseGroupingModel(initialPageData);
        $("#configure-case-grouping-form").koApplyBindings(configOptions);
    });
});