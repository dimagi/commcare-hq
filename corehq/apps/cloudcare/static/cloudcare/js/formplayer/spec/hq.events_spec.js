/* global FormplayerFrontend */
/* eslint-env mocha */
describe('HQ.Events', function() {
    describe('Receiver', function() {
        var Receiver = FormplayerFrontend.HQ.Events.Receiver,
            Actions = FormplayerFrontend.HQ.Events.Actions,
            origin = 'myorigin',
            triggerSpy,
            requestSpy,
            dummyEvent;
        beforeEach(function() {
            triggerSpy = sinon.spy();
            requestSpy = sinon.spy();
            dummyEvent = {
                origin: origin,
                data: {},
            };
            sinon.stub(FormplayerFrontend, 'trigger', triggerSpy);
            sinon.stub(FormplayerFrontend, 'request', requestSpy);
        });

        afterEach(function() {
            FormplayerFrontend.trigger.restore();
            FormplayerFrontend.request.restore();
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
            assert.throws(function() { receiver(dummyEvent); }, /Disallowed origin/);
        });

        it('should not allow no action', function() {
            var receiver = new Receiver(origin);
            assert.throws(function() { receiver(dummyEvent); }, /must have action/);
        });

        it('should not allow unknown action', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = 'unknown';
            assert.throws(function() { receiver(dummyEvent); }, /Invalid action/);
        });
    });
});
