hqDefine("geospatial/js/geo_config", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/alert_user",
], function (
    $,
    ko,
    initialPageData,
    alertUser
) {
    const ROAD_NETWORK_ALGORITHM = initialPageData.get('road_network_algorithm_slug');

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
        self.plaintext_api_token = ko.observable(data.plaintext_api_token);

        self.captureApiToken = ko.computed(function () {
            return self.selectedAlgorithm() === ROAD_NETWORK_ALGORITHM;
        });

        self.validateApiToken = function () {
            const url = "https://api.mapbox.com/directions-matrix/v1/mapbox/driving/-122.42,37.78;-122.45,37.91;-122.48,37.73";
            const params = {access_token: self.plaintext_api_token()};

            $.ajax({
                method: 'get',
                url: url,
                data: params,
                success: function () {
                    alertUser.alert_user(gettext("Token successfully verified!"), "success");
                },
            }).fail(function () {
                alertUser.alert_user(
                    gettext("Invalid API token. Please verify that the token matches the one on your Mapbox account and has the correct scope configured."),
                    "danger"
                );
            });
        };

        return self;
    };

    $(function () {
        $('#geospatial-config-form').koApplyBindings(geoConfigViewModel(initialPageData));
    });
});
