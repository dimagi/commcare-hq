describe('Reach Location Filter', function () {
    var locationModel;

    beforeEach(function () {
        locationModel = hqImport('reach/js/filters/location_filter');
    });

    it('test template', function () {
        assert.equal(locationModel.template, '<div data-bind="template: { name: \'location-template\' }"></div>')
    });
});
