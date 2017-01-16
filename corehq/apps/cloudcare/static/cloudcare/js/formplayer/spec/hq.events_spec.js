/* global FormplayerFrontend */
/* eslint-env mocha */
describe('HQ.Events', function() {
    describe('Receiver', function() {
        var Receiver = FormplayerFrontend.HQ.Events.Receiver,
            Actions = FormplayerFrontend.HQ.Events.Actions,
            origin = 'myorigin',
            triggerSpy,
            requestSpy,
            warnSpy,
            dummyEvent;
        beforeEach(function() {
            triggerSpy = sinon.spy();
            requestSpy = sinon.spy();
            warnSpy = sinon.spy();
            dummyEvent = {
                origin: origin,
                data: {},
            };
            sinon.stub(FormplayerFrontend, 'trigger', triggerSpy);
            sinon.stub(FormplayerFrontend, 'request', requestSpy);
            sinon.stub(window.console, 'warn', warnSpy);
        });

        afterEach(function() {
            FormplayerFrontend.trigger.restore();
            FormplayerFrontend.request.restore();
            window.console.warn.restore();
        });

        it('should allow the back action', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.BACK;

            receiver(dummyEvent);
            assert.isTrue(triggerSpy.called);
        });

        it('should allow the refresh action', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.REFRESH;

            receiver(dummyEvent);
            assert.isTrue(requestSpy.called);
            assert.isTrue(triggerSpy.called);
        });

        it('should not allow the wrong origin', function() {
            var receiver = new Receiver('wrong-origin');
            dummyEvent.data.action = Actions.BACK;
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });

        it('should not allow no action', function() {
            var receiver = new Receiver(origin);
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });

        it('should not allow unknown action', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = 'unknown';
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });
    });
});
