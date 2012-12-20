ko.bindingHandlers.hqbSubmitReady = {
    update: function(element, valueAccessor) {
        var value = (valueAccessor()) ? valueAccessor()() : null;
        if (value)
            $(element).addClass("btn-primary").removeClass("disabled");
        else
            $(element).addClass("disabled").removeClass("btn-primary");
    }
};

ko.bindingHandlers.fadeVisible = {
    // from knockout.js examples
    init: function(element, valueAccessor) {
        var value = valueAccessor();
        $(element).toggle(ko.utils.unwrapObservable(value));
    },
    update: function(element, valueAccessor) {
        var value = valueAccessor();
        ko.utils.unwrapObservable(value) ? $(element).fadeIn() : $(element).fadeOut();
    }
};

ko.bindingHandlers.fadeVisibleInOnly = {
    // from knockout.js examples
    init: function(element, valueAccessor) {
        var value = valueAccessor();
        $(element).toggle(ko.utils.unwrapObservable(value));
    },
    update: function(element, valueAccessor) {
        var value = valueAccessor();
        ko.utils.unwrapObservable(value) ? $(element).fadeIn() : $(element).hide();
    }
};
