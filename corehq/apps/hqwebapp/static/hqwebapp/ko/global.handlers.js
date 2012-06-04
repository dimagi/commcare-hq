ko.bindingHandlers.hqbSubmitReady = {
    update: function(element, valueAccessor) {
        var value = (valueAccessor()) ? valueAccessor()() : null;
        if (value)
            $(element).addClass("btn-primary").removeClass("disabled");
        else
            $(element).addClass("disabled").removeClass("btn-primary");
    }
};