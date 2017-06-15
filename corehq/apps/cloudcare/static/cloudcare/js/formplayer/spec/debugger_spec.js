/* globals hqImport */
/* eslint-env mocha */

describe('Debugger', function() {
    var EvaluateXPath = hqImport('cloudcare/js/debugger/debugger.js').EvaluateXPath,
        API = hqImport('cloudcare/js/debugger/debugger.js').API,
        CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger.js').CloudCareDebuggerFormEntry;

    describe('EvaluateXPath', function() {
        it('should correctly match xpath input', function() {
            var evalXPath = new EvaluateXPath(),
                result;

            result = evalXPath.matcher('', '');
            assert.equal(result, null);

            // Should match /
            result = evalXPath.matcher('', '/data');
            assert.equal(result, '/data');

            // Should not match parens
            result = evalXPath.matcher('', 'concat(');
            assert.equal(result, null);

            // Should not match queries less than 1
            result = evalXPath.matcher('', 'c');
            assert.equal(result, null);

            // Should match queries greater than 1
            result = evalXPath.matcher('', 'co');
            assert.equal(result, 'co');
        });
    });

    describe('Update logic', function() {
        var ccDebugger;

        beforeEach(function() {
            ccDebugger = new CloudCareDebugger();
            sinon.stub(API, 'evaluateXPath').returns($.Deferred());
            sinon.stub(API, 'formattedQuestions').returns($.Deferred());
            window.analytics = {
                workflow: sinon.spy(),
            };
        });

        afterEach(function() {
            API.evaluateXPath.restore();
            API.formattedQuestions.restore();
        });

        it('Should update when opened', function() {
            assert.isTrue(ccDebugger.isMinimized());

            ccDebugger.toggleState();
            assert.isFalse(ccDebugger.isMinimized());
            assert.isTrue(API.formattedQuestions.calledOnce);

            ccDebugger.toggleState();
            assert.isTrue(ccDebugger.isMinimized());
            assert.isTrue(API.formattedQuestions.calledOnce);
        });

    });
});

