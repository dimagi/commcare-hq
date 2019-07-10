hqDefine('aaa/js/filters/beneficiary_type_filter', [
    'jquery',
    'knockout',
], function (
    $,
    ko
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

            self.selectedType = ko.observable(params.postData.selectedBeneficiaryType() || null);
            self.showErrorMessage = ko.observable(false);

            params.filters[self.slug].applyFilter = function () {
                params.postData.selectedBeneficiaryType(self.selectedType() || null);
            };

            params.filters[self.slug].verify = function () {
                var isSelected = self.selectedType() !== void(0);
                self.showErrorMessage(!isSelected);
                return isSelected;
            };

            if (params.filters.hasOwnProperty(self.slug)) {
                params.filters[self.slug].resetFilters = function () {
                    self.selectedType(null);
                };
            }

            return self;
        },
        template: '<div data-bind="template: { name: \'beneficiary-type-template\' }"></div>',
    };
});
