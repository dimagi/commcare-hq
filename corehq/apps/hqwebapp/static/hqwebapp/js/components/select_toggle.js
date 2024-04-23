'use strict';
/*
 * Component for displaying a selection as a set of buttons.
 * Creates an invisible <select> element to store the value and a set of buttons for the user to interact with.
 *
 * Required parameters
 *  - options: Data to build select options. May be one of:
 *      - list of strings
 *      - list of objects with properties:
 *          - id (required)
 *          - text (required)
 *          - icon (optional)
 *      - observableArray, whose elements will be copied, so changes to the original array will not be reflected
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
            self.disabled = params.disabled || false;
            self.htmlAttrs = {};
            if (self.name) {
                self.htmlAttrs.name = self.name;
            }
            if (self.id) {
                self.htmlAttrs.id = self.id;
            }

            // Data
            self.value = ko.isObservable(params.value) ? params.value : ko.observable(params.value);
            var optionsData = ko.computed(function () {
                return ko.isObservable(params.options) ? params.options() : params.options;
            });
            self.options = ko.computed(function () {
                return ko.observableArray(_.map(optionsData(), function (o) {
                    var id = _.isString(o) ? o : o.id,
                        text = _.isString(o) ? o : o.text,
                        icon = _.isString(o) ? '' : o.icon;

                    return {
                        id: id,
                        text: text,
                        icon: icon,
                        selected: ko.computed(function () {
                            return id === self.value();
                        }),
                        click: function (model, e) {
                            if (model.id !== self.value() && !self.disabled) {
                                self.value(model.id);
                                $(e.currentTarget).closest(".ko-select-toggle").find("select").trigger("change");
                            }
                        },
                    };
                }));
            });
        },
        template: '<div data-bind="template: { name: \'ko-select-toggle\' }"></div>',
    };
});
