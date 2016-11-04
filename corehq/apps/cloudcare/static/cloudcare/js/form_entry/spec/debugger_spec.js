/* globals Formplayer */
/* eslint-env mocha */

describe('Debugger', function() {

    describe('EvaluateXPath', function() {
        it('should correctly match xpath input', function() {
            var evalXPath = new Formplayer.ViewModels.EvaluateXPath(),
                result;

            result = evalXPath.matcher('', '');
            assert.equal(result, '');

            result = evalXPath.matcher('', '/data');
            assert.equal(result, '/data');

            result = evalXPath.matcher('', 'concat(');
            assert.equal(result, '');
        });
    });
});

