hqDefine('icds/js/location_rationalization/download', [
    'jquery',
    'locations/js/utils',
], function (
    $,
    locationUtils
) {
    'use strict';
    $(function () {
        locationUtils.enableLocationSearchSelect();
    });
});
