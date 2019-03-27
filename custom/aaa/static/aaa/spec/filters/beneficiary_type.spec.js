/* global sinon */

describe('Beneficiary Type Filter', function () {
    var beneficiaryFilter;

    beforeEach(function () {
        beneficiaryFilter = hqImport('aaa/js/filters/beneficiary_type_filter');
    });

    it('test template', function () {
        assert.equal(beneficiaryFilter.template, '<div data-bind="template: { name: \'beneficiary-type-template\' }"></div>');
    });

    it('test viewModel', function () {
        var model = beneficiaryFilter.viewModel({
            filters: {
                'beneficiary-type-filter': {},
            },
            postData: {},
            disableSubmit: ko.observable(),
        });
        assert.equal(model.slug, 'beneficiary-type-filter');
        var expectedTypes = [
            {id: 'eligible_couple', name: 'Eligible Couple'},
            {id: 'pregnant_women', name: 'Pregnant Women'},
            {id: 'child', name: 'Child'},
        ];
        _.each(expectedTypes, function (element, idx) {
            assert.equal(model.beneficiaryTypes()[idx].id, element.id);
            assert.equal(model.beneficiaryTypes()[idx].name, element.name);
        });
    });
});
