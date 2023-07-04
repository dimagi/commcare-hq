'use strict';
/* eslint-env mocha */
hqDefine("cloudcare/js/formplayer/spec/user_spec", function () {
    describe('User', function () {
        describe('Collection', function () {
            it('should instantiate a user collection', function () {
                let collection = hqImport("cloudcare/js/formplayer/users/collections")([], { domain: 'mydomain' });
                assert.equal(collection.domain, 'mydomain');
            });

            it('should error on fetch a user collection', function () {
                let instantiate = function () {
                    let collection = hqImport("cloudcare/js/formplayer/users/collections")();
                    collection.fetch();
                };
                assert.throws(instantiate, /without domain/);
            });
        });

        describe('CurrentUser Model', function () {
            it('should get the display name of a mobile worker', function () {
                let model = hqImport("cloudcare/js/formplayer/users/models").CurrentUser();
                model.username = 'worker@domain.commcarehq.org';
                assert.equal(model.getDisplayUsername(), 'worker');
            });

            it('should get the display name of a web user', function () {
                let model = hqImport("cloudcare/js/formplayer/users/models").CurrentUser();
                model.username = 'web@gmail.com';
                assert.equal(model.getDisplayUsername(), 'web@gmail.com');
            });
        });

        describe('Utils', function () {
            let Utils = hqImport("cloudcare/js/formplayer/users/utils").Users,
                FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
                username = 'clark@kent.com',
                restoreAsUsername = 'worker@kent.com',
                domain = 'preview-domain',
                dummyChannel,
                dummyUser;
            beforeEach(function () {
                dummyUser = {
                    domain: domain,
                    username: username,
                };
                dummyChannel = FormplayerFrontend.getChannel();
                window.localStorage.clear();
                sinon.stub(dummyChannel, 'request').callsFake(function () { return dummyUser; });
            });

            afterEach(function () {
                window.localStorage.clear();
                dummyChannel.request.restore();
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
