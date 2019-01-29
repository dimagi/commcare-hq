hqDefine("reach/js/dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'reach/js/filters/month_year_filter',
], function (
    $,
    ko,
    _,
    monthYearFilter,
) {
    var components = {
        'month-year-filter': monthYearFilter,
    };

    $(function () {
        _.each(components, function (moduleName, elementName) {
            ko.components.register(elementName, moduleName);
        });
    });
});
