/* globals Formplayer */
/* eslint-env mocha */

describe('Debugger', function() {

    describe('EvaluateXPath', function() {
        it('should correctly match xpath input', function() {
            var evalXPath = new Formplayer.ViewModels.EvaluateXPath(),
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
        var ccDebugger,
            updateSpy;

        beforeEach(function() {
            ccDebugger = new Formplayer.ViewModels.CloudCareDebugger(),
            updateSpy = sinon.spy();
            $.subscribe('formplayer.' + Formplayer.Const.FORMATTED_QUESTIONS, updateSpy);
            window.analytics = {
                workflow: sinon.spy(),
            };
        });

        afterEach(function() {
            $.unsubscribe('formplayer.' + Formplayer.Const.FORMATTED_QUESTIONS);
        });

        it('Should update when opened', function() {
            assert.isTrue(ccDebugger.isMinimized());

            ccDebugger.toggleState();
            assert.isFalse(ccDebugger.isMinimized());
            assert.isTrue(updateSpy.calledOnce);

            ccDebugger.toggleState();
            assert.isTrue(ccDebugger.isMinimized());
            assert.isTrue(updateSpy.calledOnce);
        });

        it('Should only update when opened', function() {
            assert.isTrue(ccDebugger.isMinimized());

            $.publish('debugger.update');
            assert.isFalse(updateSpy.called);

            ccDebugger.toggleState();
            assert.isTrue(updateSpy.calledOnce);

            $.publish('debugger.update');
            // Called once on open and once on publish
            assert.isTrue(updateSpy.calledTwice);
        });
    });
});

