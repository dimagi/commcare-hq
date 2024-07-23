'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/user_spec", [
    "underscore",
    "sinon/pkg/sinon",
    "cloudcare/js/formplayer/app",
    "cloudcare/js/formplayer/users/collections",
    "cloudcare/js/formplayer/users/models",
    "cloudcare/js/formplayer/users/utils",
], function (
    _,
    sinon,
    FormplayerFrontend,
    UsersCollections,
    UsersModels,
    UsersUtils
) {
    describe('User', function () {
        describe('Collection', function () {
            it('should instantiate a user collection', function () {
                let collection = UsersCollections([], { domain: 'mydomain' });
                assert.equal(collection.domain, 'mydomain');
            });

            it('should error on fetch a user collection', function () {
                let instantiate = function () {
                    let collection = UsersCollections();
                    collection.fetch();
                };
                assert.throws(instantiate, /without domain/);
            });
        });

        describe('Display Options', function () {
            let options;
            beforeEach(function () {
                options = {
                    username: 'batman',
                    domain: 'domain',
                    apps: [],
                };
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

        describe('CurrentUser Model', function () {
            it('should get the display name of a mobile worker', function () {
                let model = UsersModels.getCurrentUser();
                model.username = 'worker@domain.commcarehq.org';
                assert.equal(model.getDisplayUsername(), 'worker');
            });

            it('should get the display name of a web user', function () {
                let model = UsersModels.getCurrentUser();
                model.username = 'web@gmail.com';
                assert.equal(model.getDisplayUsername(), 'web@gmail.com');
            });

        });

        describe('Utils', function () {
            let Utils = UsersUtils.Users,
                username = 'clark@kent.com',
                restoreAsUsername = 'worker@kent.com',
                domain = 'preview-domain',
                dummyUser;
            beforeEach(function () {
                dummyUser = {
                    domain: domain,
                    username: username,
                };
                window.localStorage.clear();
                sinon.stub(UsersModels, 'getCurrentUser').callsFake(function () { return dummyUser; });
            });

            afterEach(function () {
                window.localStorage.clear();
                UsersModels.getCurrentUser.restore();
            });

            it('should store and clear a restore as user', function () {
                assert.isNull(Utils.getRestoreAsUser(domain, username));

                Utils.logInAsUser(restoreAsUsername);

                assert.equal(Utils.getRestoreAsUser(domain, username), restoreAsUsername);

                Utils.clearRestoreAsUser(domain, username);
                assert.isNull(Utils.getRestoreAsUser(domain, username));
            });
        });
    });
});
