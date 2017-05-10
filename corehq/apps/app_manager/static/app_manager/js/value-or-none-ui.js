ko.bindingHandlers.valueOrNoneUI = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var opts = valueAccessor();
        opts.messages = opts.messages || {};
        $('span', element).each(function () {
            opts.messages[$(this).data('slug')] = $(this).html();
            $(this).hide();
        });
        $(element).find(".inner").koApplyBindings(new ValueOrNoneUI(opts));
        return {controlsDescendantBindings: true};
    }
};
