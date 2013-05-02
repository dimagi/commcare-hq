var DeletedFormsControl = function (options) {
    var self = this;
    self.is_unknown_shown = ko.observable((options.is_unknown_shown) ? 'yes': '');
    self.selected_unknown_form = ko.observable(options.selected_unknown_form);
    self.all_unknown_forms = ko.observableArray(options.all_unknown_forms);
    self.caption_text = options.caption_text;
};

$.fn.unknownFormsExtension = function (options) {
    this.each(function(i) {
        var viewModel = new DeletedFormsControl(options);
        ko.applyBindings(viewModel, $(this).get(i));
    });
};

ko.bindingHandlers.hideKnownForms = {
    update: function(element, valueAccessor) {
        var value = valueAccessor();
        var known_form = $(element).attr('data-known');
        ko.utils.unwrapObservable(value) ? $(known_form).hide() : $(known_form).show();
    }
};
