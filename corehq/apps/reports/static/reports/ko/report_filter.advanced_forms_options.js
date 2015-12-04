var DeletedFormsControl = function (options) {
    var self = this;
    self.show = ko.observable();
    self.is_unknown_shown = ko.observable((options.is_unknown_shown) ? 'yes': '');
    self.selected_unknown_form = ko.observable(options.selected_unknown_form);
    self.all_unknown_forms = ko.observableArray(options.all_unknown_forms);
    self.caption_text = options.caption_text;
    self.css_id = options.css_id;
    self.css_class = options.css_class;
};

$.fn.advanceFormsOptions = function (options) {
    this.each(function(i) {
        var viewModel = new DeletedFormsControl(options);
        $($(this).get(i)).koApplyBindings(viewModel);   // TODO: fix
        var $css_class = $('.' + viewModel.css_class);
        for (var j = 0; j < $css_class.length; j++) {
            $($css_class.get(j)).koApplyBindings(viewModel); // TODO: fix
        }

        viewModel.show.subscribe(function(newValue) {
            if (newValue) {
                $('#' + viewModel.css_id + '_status').closest('.control-group').show();
            } else {
                var $app_type_select = $('#' + viewModel.css_id + '_status');
                if ($app_type_select.val() == 'active') {
                    $('#' + viewModel.css_id + '_status').closest('.control-group').hide();
                }
                viewModel.is_unknown_shown(false);
            }
        });
        viewModel.show(options.show);
    });
};

ko.bindingHandlers.hideKnownForms = {
    update: function(element, valueAccessor) {
        var value = valueAccessor();
        var known_form = $(element).attr('data-known');
        ko.utils.unwrapObservable(value) ? $(known_form).hide() : $(known_form).show();
    }
};
