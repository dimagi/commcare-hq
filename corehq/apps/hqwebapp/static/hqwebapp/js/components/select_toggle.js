/*
 * Component for displaying a selection as a set of buttons.
 * Creates an invisible <select> element to store the value and a set of buttons for the user to interact with.
 *
 * Required parameters
 *  - options: Data to build select options. May be list of strings or list of objects with `id` and `text` properties.
 *
 * Optional parameters
 *  - name: Name of select
 *  - id: ID of select
 *  - value: initial value of select
 */

hqDefine('hqwebapp/js/components/select_toggle', [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _
) {
    return {
        viewModel: function (params) {
            var self = this;

            // Attributes passed on to the input
            self.name = params.name || '';
            self.id = params.id || '';

            // Data
            self.value = ko.observable(params.value || '');
            self.options = ko.observableArray(_.map(params.options, function (o) {
                var id = _.isString(o) ? o : o.id,
                    text = _.isString(o) ? o : o.text;

                return {
                    id: id,
                    text: text,
                    selected: ko.computed(function () {
                        return id === self.value();
                    }),
                    click: function (model, e) {
                        if (model.id !== self.value()) {
                            self.value(model.id);
                            $(e.currentTarget).closest(".ko-select-toggle").find("select").trigger("change");
                        }
                    },
                };
            }));
        },
        template: '<div data-bind="template: { name: \'ko-select-toggle\' }"></div>',
    };
});
