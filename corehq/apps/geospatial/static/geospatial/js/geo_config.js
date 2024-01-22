hqDefine("geospatial/js/geo_config", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    ko,
    initialPageData
) {
    const ROAD_NETWORK_ALGORITHM = 'road_network_algorithm';

    var geoConfigViewModel = function (configData) {
        'use strict';
        var self = {};

        var data = configData.get('config');
        self.customUserFieldName = ko.observable(data.user_location_property_name);
        self.geoCasePropertyName = ko.observable(data.case_location_property_name);

        const gpsCasePropsDepState = configData.get('gps_case_props_deprecated_state');
        let gpsCaseProps = [];
        for (const key in gpsCasePropsDepState) {
            if (!gpsCasePropsDepState[key] || key === data.case_location_property_name) {
                gpsCaseProps.push(key);
            }
        }
        self.geoCasePropOptions = ko.observableArray(gpsCaseProps);

        self.isCasePropDeprecated = ko.observable(gpsCasePropsDepState[self.geoCasePropertyName()]);
        self.savedGeoCasePropName = ko.observable(data.case_location_property_name);
        self.hasGeoCasePropChanged = ko.observable(false);

        self.onGeoCasePropChange = function () {
            if (self.geoCasePropertyName() !== self.savedGeoCasePropName()) {
                self.hasGeoCasePropChanged(true);
            } else {
                self.hasGeoCasePropChanged(false);
            }
        };

        const targetGroupingName = configData.get('target_grouping_name');
        const minMaxGroupingName = configData.get('min_max_grouping_name');
        self.selectedGroupMethod = ko.observable();
        self.isTargetGrouping = ko.computed(function () {
            return self.selectedGroupMethod() === targetGroupingName;
        });
        self.isMinMaxGrouping = ko.computed(function () {
            return self.selectedGroupMethod() === minMaxGroupingName;
        });

        self.selectedAlgorithm = ko.observable();
        self.showTokenInput = ko.computed(function () {
            return self.selectedAlgorithm() === ROAD_NETWORK_ALGORITHM;
        });

        return self;
    };

    $(function () {
        $('#geospatial-config-form').koApplyBindings(geoConfigViewModel(initialPageData));
    });
});
