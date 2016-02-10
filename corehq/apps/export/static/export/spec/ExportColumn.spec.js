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

    describe('#addTransform', function() {
        it('Should add a transform', function() {
            column = new Exports.ViewModels.ExportColumn({
                transforms: []
            });

            column.addTransform(Exports.Constants.TRANSFORMS.DATE);
            column.addTransform(Exports.Constants.TRANSFORMS.DATE);
            assert.sameMembers(column.transforms(), [Exports.Constants.TRANSFORMS.DATE]);
        });

    });

    describe('#removeTransform', function() {
        it('Should remove a transform', function() {
            column = new Exports.ViewModels.ExportColumn({
                transforms: [Exports.Constants.TRANSFORMS.DATE]
            });
            column.removeTransform(Exports.Constants.TRANSFORMS.DATE);
            column.removeTransform(Exports.Constants.TRANSFORMS.DATE);
            assert.sameMembers(column.transforms(), []);
        });
    });
});
