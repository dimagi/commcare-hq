describe('HQ.Events', function() {
    describe('Receiver', function() {
        var Receiver = FormplayerFrontend.HQ.Events.Receiver,
            Actions = FormplayerFrontend.HQ.Events.Actions,
            origin = 'myorigin',
            triggerSpy,
            dummyEvent;
        beforeEach(function() {
            triggerSpy = sinon.spy();
            dummyEvent = {
                origin: origin,
                data: {}
            };
            sinon.stub(FormplayerFrontend, 'trigger', triggerSpy);
        });

        afterEach(function() {
            FormplayerFrontend.trigger.restore();
        });

        it('should allow the back action', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.BACK;

            receiver(dummyEvent);
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

        it('should call success on success', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.BACK;
            dummyEvent.data.success = sinon.spy();
            dummyEvent.data.complete = sinon.spy();

            receiver(dummyEvent);
            assert.isTrue(dummyEvent.data.success.called);
            assert.isTrue(dummyEvent.data.complete.called);
        });

        it('should call error on error', function() {
            var receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.BACK;
            dummyEvent.data.error = sinon.spy();
            dummyEvent.data.complete = sinon.spy();

            FormplayerFrontend.trigger.restore();
            sinon.stub(FormplayerFrontend, 'trigger', function() { throw new Error('Boom'); });

            receiver(dummyEvent);
            assert.isTrue(dummyEvent.data.error.called);
            assert.isTrue(dummyEvent.data.complete.called);
        });
    });
});
