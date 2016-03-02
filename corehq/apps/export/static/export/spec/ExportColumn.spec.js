describe('ExportColumn', function() {
    it('Should properly append deidTransform', function() {
        column = new Exports.ViewModels.ExportColumn({
            transforms: ['username_transform']
        });
        column.deidTransform(Exports.Constants.DEID_OPTIONS.ID);
        assert.sameMembers(column.transforms(), ['username_transform', Exports.Constants.DEID_OPTIONS.ID]);

        column.deidTransform(Exports.Constants.DEID_OPTIONS.NONE);
        assert.sameMembers(column.transforms(), ['username_transform']);
    });
});
