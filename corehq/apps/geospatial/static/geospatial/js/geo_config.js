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

        const gpsCaseProps = configData.get('gps_case_props_deprecated_state');
        self.geoCasePropOptions = ko.observableArray(Object.keys(gpsCaseProps));

        var data = configData.get('config');
        self.customUserFieldName = ko.observable(data.user_location_property_name);
        self.geoCasePropertyName = ko.observable(data.case_location_property_name);
        self.isCasePropDeprecated = ko.observable(gpsCaseProps[self.geoCasePropertyName()]);
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
