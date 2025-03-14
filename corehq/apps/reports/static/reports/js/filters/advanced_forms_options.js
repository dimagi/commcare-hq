hqDefine('reports/js/filters/advanced_forms_options', [
    'jquery',
    'knockout',
], function (
    $,
    ko,
) {
    var deletedFormsControl = function (options) {
        var self = {};
        self.show = ko.observable();
        self.is_unknown_shown = ko.observable((options.is_unknown_shown) ? 'yes' : '');
        self.selected_unknown_form = ko.observable(options.selected_unknown_form);
        self.all_unknown_forms = ko.observableArray(options.all_unknown_forms);
        self.caption_text = options.caption_text;
        self.css_id = options.css_id;
        self.css_class = options.css_class;
        return self;
    };

    var advancedFormsOptions = function ($el, options) {
        var viewModel = deletedFormsControl(options);
        $el.koApplyBindings(viewModel);
        var $cssClass = $('.' + viewModel.css_class);
        $cssClass.each(function () {
            $(this).koApplyBindings(viewModel);
        });

        viewModel.show.subscribe(function (newValue) {
            if (newValue) {
                $('#' + viewModel.css_id + '_status').closest('.form-group').show();
            } else {
                var $appTypeSelect = $('#' + viewModel.css_id + '_status');
                if ($appTypeSelect.val() === 'active') {
                    $('#' + viewModel.css_id + '_status').closest('.form-group').hide();
                }
                viewModel.is_unknown_shown('');
            }
        });
        viewModel.show(options.show);
    };

    ko.bindingHandlers.hideKnownForms = {
        update: function (element, valueAccessor) {
            var value = valueAccessor();
            var knownForm = $(element).attr('data-known');
            ko.utils.unwrapObservable(value) ? $(knownForm).hide() : $(knownForm).show();
        },
    };

    return { advancedFormsOptions: advancedFormsOptions };
});
