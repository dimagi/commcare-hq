function ValueOrNoneUI(opts) {
    var self = this;
    var wrapObservable = function (o) {
        if (ko.isObservable(o)) {
            return o;
        } else {
            return ko.observable(o);
        }
    };

    self.messages = opts.messages;
    self.allowed = wrapObservable(opts.allowed);
    self.inputValue = wrapObservable(opts.value || '');
    self.hasValue = ko.observable(!!self.inputValue());
}

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
