hqDefine("geospatial/js/geo_config", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    ko,
    initialPageData,
) {
    const CUSTOM_USER_PROP = "custom_user_property";

    var geoConfigViewModel = function (configData) {
        'use strict';
        var self = {};

        var data = configData.get('config')
        self.customUserFieldName = ko.observable(data.user_location_property_name);
        self.geoCasePropertyName = ko.observable(data.case_location_property_name);

        return self;
    }

    $(function () {
        $('#geospatial-config-form').koApplyBindings(geoConfigViewModel(initialPageData));
    });
});
