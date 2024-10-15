'use strict';
/*
 * Component for displaying a search box. Almost certainly included within a a larger knockout template.
 *
 * Required parameters
 *  - value: Observable for the query value
 *  - action: Function to call on search
 *
 * Optional parameters
 *  - placeholder: String.
 *  - immediate: Boolean. If true, search on every keypress.
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
    const component = {
        viewModel: function (params) {
            var self = {};

            self.value = params.value;
            self.action = params.action;
            self.placeholder = params.placeholder || '';
            self.immediate = params.immediate;

            self.clickAction = function () {
                self.action();
            };
            self.keypressAction = function (model, e) {
                if (e.keyCode === 13) {
                    self.action();
                }
                return true;
            };
            if (self.immediate) {
                self.value.subscribe(_.debounce(function () {
                    self.action();
                }, 200));
            }

            self.clearQuery = function () {
                self.value('');
                self.action();
            };

            return self;
        },
        template: '<div data-bind="template: { name: \'ko-search-box-template\' }"></div>',
    };

    ko.components.register('search-box', component);

    $(function () {
        _.each($('search-box'), function (el) {
            var $el = $(el);
            if ($el.data('apply-bindings') !== false) {
                $(el).koApplyBindings();
            }
        });
    });

    return component;
});
