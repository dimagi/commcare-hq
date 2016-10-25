/* global FormplayerFrontend */
/* eslint-env mocha */
describe('User', function () {
    describe('Collection', function() {
        var UserCollection = FormplayerFrontend.Collections.User
        it('should instantiate a user collection', function() {
            var collection = new UserCollection([], { domain: 'mydomain' })
            assert.equal(collection.domain, 'mydomain');
        });

        it('should error on fetch a user collection', function() {
            var instantiate = function() {
                var collection = new UserCollection();
                collection.fetch();
            };
            assert.throws(instantiate, /without domain/);
        });
    });
});
