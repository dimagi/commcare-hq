/* global FormplayerFrontend */
/* eslint-env mocha */
describe('User', function () {
    describe('Collection', function () {
        it('should instantiate a user collection', function () {
            var collection = hqImport("cloudcare/js/formplayer/users/collections")([], { domain: 'mydomain' });
            assert.equal(collection.domain, 'mydomain');
        });

        it('should error on fetch a user collection', function () {
            var instantiate = function () {
                var collection = hqImport("cloudcare/js/formplayer/users/collections")();
                collection.fetch();
            };
            assert.throws(instantiate, /without domain/);
        });
    });

    describe('CurrentUser Model', function () {
        it('should get the display name of a mobile worker', function () {
            var model = new FormplayerFrontend.Users.Models.CurrentUser();
            model.username = 'worker@domain.commcarehq.org';
            assert.equal(model.getDisplayUsername(), 'worker');
        });

        it('should get the display name of a web user', function () {
            var model = new FormplayerFrontend.Users.Models.CurrentUser();
            model.username = 'web@gmail.com';
            assert.equal(model.getDisplayUsername(), 'web@gmail.com');
        });

    });

    describe('Utils', function () {
        var Utils = hqImport("cloudcare/js/formplayer/users/utils").Users,
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
            sinon.stub(FormplayerFrontend, 'request').callsFake(function () { return dummyUser; });
        });

        afterEach(function () {
            window.localStorage.clear();
            FormplayerFrontend.request.restore();
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
