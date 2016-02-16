describe('Export Utility functions', function() {

    describe('#getTagCSSClass', function() {
        it('Should get regular tag class', function() {
            var cls = Exports.Utils.getTagCSSClass('random-tag');
            assert.equal(cls, 'label');
        });

        it('Should get warning tag class', function() {
            var cls = Exports.Utils.getTagCSSClass(Exports.Constants.TAG_DELETED);
            assert.equal(cls, 'label label-warning');
        });
    });

    describe('#removeDeidTransforms', function() {
        it('Should remove all deid transforms', function() {
            result = Exports.Utils.removeDeidTransforms(['deid_id', 'username_transform']);
            assert.sameMembers(result, ['username_transform']);
        });
    });
});
