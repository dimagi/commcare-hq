describe('Export Utility functions', function() {
    var constants = hqImport('export/js/const.js');
    describe('#getTagCSSClass', function() {
        it('Should get regular tag class', function() {
            var cls = Exports.Utils.getTagCSSClass('random-tag');
            assert.equal(cls, 'label label-default');
        });

        it('Should get warning tag class', function() {
            var cls = Exports.Utils.getTagCSSClass(constants.TAG_DELETED);
            assert.equal(cls, 'label label-warning');
        });
    });
});
