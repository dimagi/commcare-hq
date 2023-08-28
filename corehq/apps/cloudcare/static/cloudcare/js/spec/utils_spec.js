/* eslint-env mocha */
hqDefine("cloudcare/js/spec/utils_spec", function () {
    describe("Cloudcare Utils", function () {
        const constants = hqImport("cloudcare/js/formplayer/constants"),
            utils = hqImport("cloudcare/js/utils");

        describe('Small Screen Listener', function () {
            it('should initially enable small screen mode in small window', function () {
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX;
                const smallScreenEnabled = utils.watchSmallScreenEnabled(function () {});
                assert.isTrue(smallScreenEnabled);
            });

            it('should initially disable small screen mode in large window', function () {
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX + 1;
                const smallScreenEnabled = utils.watchSmallScreenEnabled(function () {});
                assert.isFalse(smallScreenEnabled);
            });

            it('should update small screen mode on window resize', function () {
                let smallScreenEnabled = utils.watchSmallScreenEnabled(enabled => smallScreenEnabled = enabled);
                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX;
                $(window).trigger("resize");
                assert.isTrue(smallScreenEnabled);

                window.innerWidth = constants.SMALL_SCREEN_WIDTH_PX + 1;
                $(window).trigger("resize");
                assert.isFalse(smallScreenEnabled);
            });
        });
    });
});
