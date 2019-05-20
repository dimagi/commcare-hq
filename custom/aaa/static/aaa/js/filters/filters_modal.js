hqDefine('aaa/js/filters/filters_modal', [
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
            self.filters = params.filters;
            self.postData = params.postData;
            self.callback = params.callback;
            self.localStorage = params.localStorage;

            self.resetFilter = function () {
                _.each(self.filters, function (filter) {
                    if (filter.hasOwnProperty('resetFilters')) {
                        filter.resetFilters();
                    }
                });
            };

            self.applyFilters = function () {
                var allFiltersSelected = true;

                _.each(self.filters, function (filter) {
                    if (!filter.verify()) {
                        allFiltersSelected = false;
                    }
                });

                if (allFiltersSelected) {
                    _.each(self.filters, function (filter) {
                        if (filter.hasOwnProperty('applyFilter')) {
                            filter.applyFilter();
                        }
                    });
                    var urlParams = [];
                    _.each(self.postData, function (value, key) {
                        var val = _.isFunction(value) ? value() : value;
                        urlParams.push(key + '=' + (val || ''));
                    });
                    history.pushState('', '', '?' + urlParams.join('&'));

                    self.localStorage.showModal(false);
                    params.callback();
                }
            };

            self.hideFilter = function (filterSlug) {
                return !self.filters.hasOwnProperty(filterSlug);
            };

            var paramsString = window.location.href.split("?")[1];
            if (paramsString !== void(0)) {
                self.localStorage.showModal(false);
                params.callback();
            }

            return self;
        },
        template: '<div data-bind="template: { name: \'filters-modal-template\' }"></div>',
    };
});
