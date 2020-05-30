/* eslint-env mocha */

describe('inactivity', function () {
    var module = hqImport("hqwebapp/js/inactivity"),
        timeout = 10 * 60 * 1000;   // 10-minute timeout

    describe('inactivityTimeout', function () {
        it('should use timeout when lastRequest is not provided', function () {
            // last request unknown => 10 minutes left
            var response = module.calculateDelayAndWarning(timeout);
            assert.equal(response.delay, 8 * 60 * 1000);
            assert.isFalse(response.show_warning);
        });

        it('should ping when there are 2 minutes left', function () {
            // last request 5 minutes ago => 1 minute left
            var response = module.calculateDelayAndWarning(timeout, new Date() - 5 * 60 * 1000);
            assert.equal(response.delay, 3 * 60 * 1000);
            assert.isFalse(response.show_warning);
        });

        it('should warn and ping every 10 seconds in the last 2 minutes', function () {
            // last request 9 minutes ago => 1 minute left
            var response = module.calculateDelayAndWarning(timeout, new Date() - 9 * 60 * 1000);
            assert.equal(response.delay, 10 * 1000);
            assert.isTrue(response.show_warning);
        });

        it('should warn and ping every 3 seconds in the last 30 seconds', function () {
            // last request 9:45 ago => 15 seconds left
            var response = module.calculateDelayAndWarning(timeout, new Date() - 9.75 * 60 * 1000);
            assert.equal(response.delay, 3 * 1000);
            assert.isTrue(response.show_warning);
        });
    });
});
