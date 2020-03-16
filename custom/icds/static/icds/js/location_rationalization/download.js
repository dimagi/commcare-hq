hqDefine('icds/js/location_rationalization/download', [
    'jquery',
    'locations/js/utils',
    'hqwebapp/js/widgets', // using select2/dist/js/select2.full.min for ko-select2 on location select
], function (
    $,
    locationUtils
) {
    'use strict';
    $(function () {
        locationUtils.enableLocationSearchSelect();
    });
});
