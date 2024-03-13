/* eslint-env mocha */
hqDefine("hqwebapp/spec/bootstrap3/inactivity_spec", [
    'hqwebapp/js/bootstrap3/inactivity',
], function (
    module
) {
    describe('inactivity', function () {
        var tolerantAssert = function (expected, actual) {
            expected = Math.round(expected / 10);
            actual = Math.round(actual / 10);
            assert.equal(expected, actual);
        };

        var responseForFutureExpiration = function (minutes) {
            return module.calculateDelayAndWarning(new Date() * 1 + minutes * 60 * 1000);
        };

        describe('inactivityTimeout', function () {
            it('should ping in 10 minutes if expiryDate is unknown', function () {
                // last request unknown => 8 minutes left
                var response = module.calculateDelayAndWarning();
                tolerantAssert(response.delay, 8 * 60 * 1000);
                assert.isFalse(response.show_warning);
            });

            it('should ping when there are 2 minutes left', function () {
                // expiring in 5 minutes => ping in 3 minutes
                var response = responseForFutureExpiration(5);
                tolerantAssert(response.delay, 3 * 60 * 1000);
                assert.isFalse(response.show_warning);
            });

            it('should warn and ping every 10 seconds in the last 2 minutes', function () {
                var response = responseForFutureExpiration(1);
                tolerantAssert(response.delay, 10 * 1000);
                assert.isTrue(response.show_warning);
            });

            it('should warn and ping every 3 seconds in the last 30 seconds', function () {
                var response = responseForFutureExpiration(0.25);
                tolerantAssert(response.delay, 3 * 1000);
                assert.isTrue(response.show_warning);
            });

            it('should use absolute value in case session appears expired', function () {
                var response = responseForFutureExpiration(-5);
                tolerantAssert(response.delay, 3 * 60 * 1000);
                assert.isFalse(response.show_warning);
            });

            it('should use absolute value in case session is very expired', function () {
                var response = responseForFutureExpiration(-20);
                tolerantAssert(response.delay, 18 * 60 * 1000);
                assert.isFalse(response.show_warning);
            });
        });
    });
});
