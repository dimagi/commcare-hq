'use strict';
/* global Backbone */
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/integration_spec", function () {
    describe('FormplayerFrontend Integration', function () {
        let FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
            UsersModels = hqImport("cloudcare/js/formplayer/users/models");

        describe('Start up', function () {
            let options,
                server;
            beforeEach(function () {
                server = sinon.useFakeXMLHttpRequest();
                options = {
                    username: 'batman',
                    domain: 'domain',
                    apps: [],
                };
                sinon.stub(Backbone.history, 'start').callsFake(sinon.spy());

                // Prevent showing views, which doesn't work properly in tests
                FormplayerFrontend.off("before:start");
                FormplayerFrontend.regions = {
                    getRegion: function () {
                        return {
                            show: function () {
                                return;
                            },
                        };
                    },
                };
            });

            afterEach(function () {
                server.restore();
                Backbone.history.start.restore();
            });

            it('should start the formplayer frontend app', function () {
                FormplayerFrontend.start(options);

                let user = UsersModels.getCurrentUser();
                assert.equal(user.username, options.username);
                assert.equal(user.domain, options.domain);
            });

            it('should correctly restore display options', function () {
                let newOptions = _.clone(options),
                    user;
                newOptions.phoneMode = true;
                newOptions.oneQuestionPerScreen = true;
                newOptions.language = 'sindarin';

                FormplayerFrontend.start(newOptions);

                user = UsersModels.getCurrentUser();
                hqImport("cloudcare/js/formplayer/utils/utils").saveDisplayOptions(user.displayOptions);

                // New session, but old options
                FormplayerFrontend.start(options);
                user = UsersModels.getCurrentUser();

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
});
