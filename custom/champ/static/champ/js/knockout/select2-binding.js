ko.bindingHandlers.select2 = {
    init: function (element, valueAccessor) {
        $(element).select2(valueAccessor());
        ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
            $(element).select2('destroy');
        });
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        var allBindings = allBindingsAccessor(),
            value = ko.utils.unwrapObservable(allBindings.value || allBindings.selectedOptions);
        if (value) {
            $(element).val(value).trigger('change');
        } else {
            $(element).select2();
        }
    },
};
