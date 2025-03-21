import sinon from "sinon";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import hqEvents from "cloudcare/js/formplayer/hq_events";

describe('HQ Events', function () {
    describe('Receiver', function () {
        let Receiver = hqEvents.Receiver,
            Actions = hqEvents.Actions,
            origin = 'myorigin',
            triggerSpy,
            requestSpy,
            warnSpy,
            dummyChannel,
            dummyEvent;
        beforeEach(function () {
            triggerSpy = sinon.spy();
            requestSpy = sinon.spy();
            warnSpy = sinon.spy();
            dummyChannel = FormplayerFrontend.getChannel();
            dummyEvent = {
                origin: origin,
                data: {},
            };
            sinon.stub(FormplayerFrontend, 'trigger').callsFake(triggerSpy);
            sinon.stub(dummyChannel, 'request').callsFake(requestSpy);
            sinon.stub(window.console, 'warn').callsFake(warnSpy);
        });

        afterEach(function () {
            FormplayerFrontend.trigger.restore();
            dummyChannel.request.restore();
            window.console.warn.restore();
        });

        it('should allow the back action', function () {
            let receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.BACK;

            receiver(dummyEvent);
            assert.isTrue(triggerSpy.called);
            assert.isTrue(triggerSpy.calledWith("navigation:back"));
        });

        it('should allow the refresh action', function () {
            let receiver = new Receiver(origin);
            dummyEvent.data.action = Actions.REFRESH;

            receiver(dummyEvent);
            assert.isTrue(requestSpy.called);
            assert.isTrue(triggerSpy.called);
            assert.isTrue(triggerSpy.calledWith("refreshApplication"));
        });

        it('should not allow the wrong origin', function () {
            let receiver = new Receiver('wrong-origin');
            dummyEvent.data.action = Actions.BACK;
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });

        it('should not allow no action', function () {
            let receiver = new Receiver(origin);
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });

        it('should not allow unknown action', function () {
            let receiver = new Receiver(origin);
            dummyEvent.data.action = 'unknown';
            receiver(dummyEvent);
            assert.isTrue(warnSpy.called);
        });
    });
});
