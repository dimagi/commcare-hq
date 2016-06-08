describe('Export Utility functions', function() {
    var constants = hqImport('export/js/const.js');
    var utils = hqImport('export/js/utils.js');

    describe('#getTagCSSClass', function() {
        it('Should get regular tag class', function() {
            var cls = utils.getTagCSSClass('random-tag');
            assert.equal(cls, 'label label-default');
        });

        it('Should get warning tag class', function() {
            var cls = utils.getTagCSSClass(constants.TAG_DELETED);
            assert.equal(cls, 'label label-warning');
        });
    });
});
