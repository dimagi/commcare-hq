/*
 * Component for TODO
 *
 * Required parameters
 *  - options
 *
 * Optional parameters
 *  - name
 *  - id
 *  - value
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
                    click: function (model) {
                        self.value(model.id);
                    },
                };
            }));
        },
        template: '<div data-bind="template: { name: \'ko-select-toggle\' }"></div>',
    };
});
