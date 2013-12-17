ko.bindingHandlers.isPrevNextDisabled = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value === undefined) {
            $(element).parent().addClass('disabled');
        } else {
            $(element).parent().removeClass('disabled');
        }
    }
};

ko.bindingHandlers.isPaginationActive = {
    update: function(element, valueAccessor, allBindingsAccessor) {
        var current_page = parseInt(valueAccessor()());
        var current_item = parseInt(allBindingsAccessor()['text']);
        if (current_page === current_item) {
            $(element).parent().addClass('active');
        } else {
            $(element).parent().removeClass('active');
        }
    }
};
