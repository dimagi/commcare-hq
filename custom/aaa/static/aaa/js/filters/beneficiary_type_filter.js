hqDefine('aaa/js/filters/beneficiary_type_filter', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
], function (
    $,
    ko,
    _,
    moment
) {
    return {
        viewModel: function (params) {
            var self = {};
            self.slug = 'beneficiary-type-filter';

            self.beneficiaryTypes = ko.observableArray([
                {id: 'eligible_couple', name: 'Eligible Couple'},
                {id: 'pregnant_women', name: 'Pregnant Women'},
                {id: 'child', name: 'Child'},
            ]);

            self.selectedType = ko.observable();

            params.disableSubmit(true);

            self.selectedType.subscribe(function (newValue) {
                params.disableSubmit(newValue === null);
            });

            params.filters[self.slug].applyFilter = function () {
                params.postData.selectedBeneficiaryType(self.selectedType() || null);
            };

            if (params.filters.hasOwnProperty(self.slug)) {
                params.filters[self.slug].resetFilters = function () {
                    self.selectedType(null);
                };
            }

            return self
        },
        template: '<div data-bind="template: { name: \'beneficiary-type-template\' }"></div>',
    };
});
