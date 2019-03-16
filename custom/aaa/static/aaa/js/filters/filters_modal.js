hqDefine('aaa/js/filters/filters_modal', [
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
            self.filters = params.filters;
            self.postData = params.postData;
            self.callback = params.callback;
            self.localStorage = params.localStorage;

            self.disableSubmit = ko.observable(false);

            self.resetFilter = function () {
                _.each(self.filters, function (filter) {
                    if(filter.hasOwnProperty('resetFilters')) {
                        filter.resetFilters();
                    }
                });
            };

            self.applyFilters = function () {
                _.each(self.filters, function (filter) {
                    if(filter.hasOwnProperty('applyFilter')) {
                        filter.applyFilter();
                    }
                });
                self.localStorage.showModal(false);
                params.callback();
            };

            self.hideFilter = function (filterSlug) {
                return !self.filters.hasOwnProperty(filterSlug);
            };
            return self;
        },
        template: '<div data-bind="template: { name: \'filters-modal-template\' }"></div>',
    };
});
