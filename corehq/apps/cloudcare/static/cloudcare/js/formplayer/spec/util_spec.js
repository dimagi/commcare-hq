/* global Util */
/* eslint-env mocha */

describe('Util', function() {
    describe('#displayOptions', function() {
        beforeEach(function() {
            sinon.stub(Util, 'getDisplayOptionsKey', function() { return 'mykey'; });
            window.localStorage.clear();
        });

        afterEach(function() {
            Util.getDisplayOptionsKey.restore();
        });

        it('should retrieve saved display options', function() {
            var options = { option: 'yes' };
            Util.saveDisplayOptions(options);
            assert.deepEqual(Util.getSavedDisplayOptions(), options);
        });

        it('should not fail on bad json saved', function() {
            localStorage.setItem(Util.getDisplayOptionsKey(), 'bad json');
            assert.deepEqual(Util.getSavedDisplayOptions(), {});
        });

    });
});
