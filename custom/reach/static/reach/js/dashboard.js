hqDefine("reach/js/dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'reach/js/filters/month_year_filter',
    'reach/js/filters/location_filter',
], function (
    $,
    ko,
    _,
    monthYearFilter,
    locationFilter
) {
    var components = {
        'month-year-filter': monthYearFilter,
        'location-filter': locationFilter,
    };

    $(function () {
        _.each(components, function (moduleName, elementName) {
            ko.components.register(elementName, moduleName);
        });
    });
});
