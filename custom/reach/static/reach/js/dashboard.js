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

        ko.bindingHandlers.select2 = {
            init: function (element, valueAccessor) {
                $(element).select2(valueAccessor());
                ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                    $(element).select2('destroy');
                });
            },
            update:function(element, valueAccessor, allBindingsAccessor) {
                var allBindings = allBindingsAccessor(),
                value = ko.utils.unwrapObservable(allBindings.value || allBindings.selectedOptions);
                if (value) {
                    $(element).select2('val', value).trigger('change');
                } else {
                    $(element).select2();
                }
            }
        };

    });
});
