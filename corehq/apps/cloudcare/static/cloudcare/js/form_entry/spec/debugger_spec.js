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

