'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/spec/utils_spec", [
    "sinon/pkg/sinon",
    "cloudcare/js/formplayer/constants",
    "cloudcare/js/utils",
], function (
    sinon,
    constants,
    utils
) {
    describe("Cloudcare Utils", function () {
        describe('Small Screen Listener', function () {
            const callback = sinon.stub().callsFake(smallScreenEnabled => smallScreenEnabled);
            const smallScreenListener = utils.smallScreenListener(callback);

            beforeEach(function () {
                smallScreenListener.listen();
            });

            afterEach(function () {
                smallScreenListener.stopListening();
                callback.resetHistory();
            });

            it('should run callback once on listener initialize', function () {
                assert.isTrue(callback.calledOnce);
            });

            it('should run callback with smallScreenEnabled = true in small window', function () {
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX - 1;
                $(window).trigger("resize");
                assert.isTrue(callback.lastCall.calledWith(true));
            });

            it('should run callback with smallScreenEnabled = false in large window', function () {
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX + 1;
                $(window).trigger("resize");
                assert.isTrue(callback.lastCall.calledWith(false));
            });

            it('should run callback with new smallScreenEnabled value when small screen threshold crossed', function () {
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX - 1;
                $(window).trigger("resize");
                assert.isTrue(callback.lastCall.calledWith(true));

                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX + 1;
                $(window).trigger("resize");
                assert.isTrue(callback.lastCall.calledWith(false));
            });
        });
    });
});
