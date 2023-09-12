hqDefine("geospatial/js/geo_config", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    ko,
    initialPageData
) {
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

        return self;
    };

    $(function () {
        $('#geospatial-config-form').koApplyBindings(geoConfigViewModel(initialPageData));
    });
});
