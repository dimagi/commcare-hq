/* eslint-env mocha */

describe('Util', function () {
    var Util = hqImport("cloudcare/js/formplayer/utils/util");

    describe('#displayOptions', function () {
        beforeEach(function () {
            sinon.stub(Util, 'getDisplayOptionsKey').callsFake(function () { return 'mykey'; });
            window.localStorage.clear();
        });

        afterEach(function () {
            Util.getDisplayOptionsKey.restore();
        });

        it('should retrieve saved display options', function () {
            var options = { option: 'yes' };
            Util.saveDisplayOptions(options);
            assert.deepEqual(Util.getSavedDisplayOptions(), options);
        });

        it('should not fail on bad json saved', function () {
            localStorage.setItem(Util.getDisplayOptionsKey(), 'bad json');
            assert.deepEqual(Util.getSavedDisplayOptions(), {});
        });

    });

    describe('#pagesToShow', function () {
        it('should only show totalPages if less than limit', function () {
            var result = Util.pagesToShow(1, 5, 10);
            assert.equal(result.start, 0);
            assert.equal(result.end, 5);
        });

        it('should start at 0 when less than half the limit', function () {
            var result = Util.pagesToShow(3, 12, 10);
            assert.equal(result.start, 0);
            assert.equal(result.end, 10);
        });

        it('should end at totalPages when less than half the limit from totalPages', function () {
            var result = Util.pagesToShow(17, 20, 10);
            assert.equal(result.start, 10);
            assert.equal(result.end, 20);
        });

        it('should show selectedPage in the middle', function () {
            var result = Util.pagesToShow(17, 50, 10);
            assert.equal(result.start, 12);
            assert.equal(result.end, 22);
        });
    });
});
