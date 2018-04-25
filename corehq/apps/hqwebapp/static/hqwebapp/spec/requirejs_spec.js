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
            'hqwebapp/js/initial_page_data',
            'analytix/js/google',
            'analytix/js/kissmetrix',
        ], function(
            initialPageData,
            google,
            kissmetrics
        ) {
            initialPageData.reverse = function(path) {
                return path;
            };
            google.track.event = sinon.spy();
            google.track.click = sinon.spy();
            kissmetrics.track.event = sinon.spy();

            // Prevent modules from throwing errors when loaded in this artificial context
            $.holdReady(true);

            $.ajax({
                dataType: "json",
                url: "/static/hqwebapp/spec/requirejs_main.json",
                success: function(dependencies) {
                    requirejs(dependencies, function() {
                        done();
                    }, function(err) {
                        assert.fail(err);
                    });
                },
            });
        });
    });
});
