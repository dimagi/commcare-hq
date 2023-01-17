'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/integration_spec", [
    "underscore",
    "backbone",
    "sinon/pkg/sinon",
    "cloudcare/js/formplayer/app",
    "cloudcare/js/formplayer/users/models",
    "cloudcare/js/formplayer/utils/utils",
], function (
    _,
    Backbone,
    sinon,
    FormplayerFrontend,
    UsersModels
) {
    describe('FormplayerFrontend Integration', function () {
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

            it('should initialize user', function () {
                UsersModels.setCurrentUser(options);

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

                UsersModels.setCurrentUser(newOptions);

                user = UsersModels.getCurrentUser();
                UsersModels.saveDisplayOptions(user.displayOptions);

                // New session, but old options
                UsersModels.setCurrentUser(options);
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
