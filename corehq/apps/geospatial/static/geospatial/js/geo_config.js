hqDefine("geospatial/js/geo_config", [
    "jquery",
    "knockout",
//    "hqwebapp/js/initial_page_data",
], function (
    $,
    ko,
//    initialPageData,
) {
    const USER_MODEL = "user_model";

    var geoConfigViewModel = function () {
        'use strict';
        var self = {};

        self.locationSourceOption = ko.observable();
        self.customUserFieldName = ko.observable();
        self.geoCasePropertyName = ko.observable();

        self.showCustomField = ko.computed(function () {
            return self.locationSourceOption() === USER_MODEL;
        });

        return self;
    }

    $(function () {
        $('#geospatial-config-form').koApplyBindings(geoConfigViewModel());
    });
});
