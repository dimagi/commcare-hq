hqDefine("aaa/js/dashboard", [
    'jquery',
    'knockout',
    'underscore',
    'aaa/js/filters/filters_modal',
    'aaa/js/filters/month_year_filter',
    'aaa/js/filters/location_filter',
    'aaa/js/filters/beneficiary_type_filter',
], function (
    $,
    ko,
    _,
    filtersModal,
    monthYearFilter,
    locationFilter,
    beneficiaryTypeFilter
) {
    var components = {
        'filters-modal': filtersModal,
        'month-year-filter': monthYearFilter,
        'location-filter': locationFilter,
        'beneficiary-type-filter': beneficiaryTypeFilter,
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

    ko.bindingHandlers.select2 = new function () {
        this.init = function (element, valueAccessor) {
            var $el = $(element);
            var params = {
                width: "element",
            };

            $el.select2(Object.assign(params, valueAccessor()));
        };

        this.update = function (element, valueAccessor, allBindings) {
            $(element).val(ko.unwrap(allBindings().value)).trigger("change");
        };
    }();

    Object.assign($.fn.dataTableExt.oStdClasses, {
        "sLengthSelect": "form-control"
    });

    $(function () {
        _.each(components, function (moduleName, elementName) {
            ko.components.register(elementName, moduleName);
        });
    });
});
