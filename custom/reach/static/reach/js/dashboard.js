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

    ko.subscribable.fn.subscribeChanged = function (callback) {
         var oldValue;
         this.subscribe(function (_oldValue) {
             oldValue = _oldValue;
         }, this, 'beforeChange');

         this.subscribe(function (newValue) {
             callback(newValue, oldValue);
         });
    };

    $(function () {
        _.each(components, function (moduleName, elementName) {
            ko.components.register(elementName, moduleName);
        });
    });
});
