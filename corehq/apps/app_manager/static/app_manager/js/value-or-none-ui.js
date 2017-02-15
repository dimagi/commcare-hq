ko.bindingHandlers.valueOrNoneUI = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var opts = valueAccessor(),
            helper;
        opts.messages = opts.messages || {};
        $('span', element).each(function () {
            opts.messages[$(this).data('slug')] = $(this).html();
            $(this).hide();
        });
        helper = new ValueOrNoneUI(opts);
        var subElement = $('<div></div>').attr(
            'data-bind',
            "template: 'value-or-none-ui-template'"
        ).appendTo(element);
        subElement.koApplyBindings(helper);
        return {controlsDescendantBindings: true};
    }
};
