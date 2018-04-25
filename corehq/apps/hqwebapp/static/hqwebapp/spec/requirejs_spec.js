/* eslint-env mocha */
/* global $, sinon */

describe('requirejs', function() {
    it('should load modules', function(done) {
        requirejs.config({
            deps: ['knockout', 'ko.mapping'],
            callback: function (ko, mapping) {
                ko.mapping = mapping;
            },
        });
        requirejs([
            'analytix/js/google',
            'analytix/js/kissmetrix',
        ], function(
            google,
            kissmetrics,
        ) {
            google.track.event = sinon.spy();
            google.track.click = sinon.spy();
            kissmetrics.track.event = sinon.spy();

            requirejs([
                'fixtures/js/view-table',
            ], function() {
                done();
            }, function(err) {
                assert.fail(err);
            });
        });
    });
});
