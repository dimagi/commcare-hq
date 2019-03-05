/*
 * Component for TODO
 *
 * Optional parameters
 *  - TODO
 */

hqDefine('hqwebapp/js/components/search_box', [
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
            var self = {};

            // Attributes passed on to the input
            self.value = params.value;
            self.action = params.action;
            self.placeholder = params.placeholder || '';

            self.clickAction = params.action;
            self.keypressAction = function (model, e) {
                if (event.keyCode === 13) {
                    self.action();
                }
                return true;
            };

            self.clearQuery = function () {
                self.value('');
                self.action();
            };

            return self;
        },
        template: '<div data-bind="template: { name: \'ko-search-box-template\' }"></div>',
    };
});
