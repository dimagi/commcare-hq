/* eslint-env mocha */
describe('Render a case list', function() {

    describe('#getMenus', function () {

        beforeEach(function() {

        });

        it('Should get regular tag class', function () {
            var cls = utils.getTagCSSClass('random-tag');
            assert.equal(cls, 'label label-default');
        });
    });
});