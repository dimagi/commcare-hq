/* global FormplayerFrontend, Util, Backbone */
/* eslint-env mocha */

describe('FormplayerFrontend Integration', function() {
    describe('Start up', function() {
        var options,
            server;
        beforeEach(function() {
            server = sinon.useFakeXMLHttpRequest();
            options = {
                username: 'batman',
                domain: 'domain',
                apps: [],
            };
            sinon.stub(Backbone.history, 'start', sinon.spy());
        });

        afterEach(function() {
            server.restore();
            Backbone.history.start.restore();
        });

        it('should start the formplayer frontend app', function() {
            FormplayerFrontend.start(options);

            var user = FormplayerFrontend.request('currentUser');
            assert.equal(user.username, options.username);
            assert.equal(user.domain, options.domain);
        });

        it('should correctly restore display options', function() {
            var newOptions = _.clone(options),
                user;
            newOptions.phoneMode = true;
            newOptions.oneQuestionPerScreen = true;
            newOptions.language = 'sindarin';

            FormplayerFrontend.start(newOptions);

            user = FormplayerFrontend.request('currentUser');
            Util.saveDisplayOptions(user.displayOptions);

            // New session, but old options
            FormplayerFrontend.start(options);
            user = FormplayerFrontend.request('currentUser');

            assert.deepEqual(user.displayOptions, {
                phoneMode: undefined, // we don't store this option
                singleAppMode: undefined,
                landingPageAppMode: undefined,
                oneQuestionPerScreen: true,
                language: 'sindarin',
            });
        });
    });
});
