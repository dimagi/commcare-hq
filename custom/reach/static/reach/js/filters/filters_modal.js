hqDefine('reach/js/filters/filters_modal', [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _,
) {
    return {
        viewModel: function (params) {
            var self = {};
            self.showFilter = ko.observable(false);
            self.filters = params.filters;
            self.postData = params.postData;
            self.callback = params.callback;
            self.localStorage = params.localStorage;
            self.resetFilter = function () {
                _.each(self.filters, function (filter) {
                    if(filter.hasOwnProperty('resetFilters')) {
                        filter.resetFilters();
                    }
                });
            };

            self.applyFilters = function () {
                self.showFilter(false);
                params.callback();
            };
            return self;
        },
        template: '<div data-bind="template: { name: \'filters-modal-template\' }"></div>',
    };
});
