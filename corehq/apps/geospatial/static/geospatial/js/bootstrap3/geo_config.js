

import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";

var geoConfigViewModel = function (configData) {
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

    self.minCasesPerUser = ko.observable(data.min_cases_per_user);
    self.maxCasesPerUser = ko.observable(data.max_cases_per_user);

    self.maxCaseDistance = ko.observable(data.max_case_distance);
    self.maxTravelTime = ko.observable(data.max_case_travel_time);
    self.flagAssignedCases = ko.observable(data.flag_assigned_cases);

    return self;
};

$(function () {
    $('#geospatial-config-form').koApplyBindings(geoConfigViewModel(initialPageData));
});
