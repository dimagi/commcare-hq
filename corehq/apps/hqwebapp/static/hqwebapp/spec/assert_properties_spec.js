/* eslint-env mocha */
/* global $, sinon */

describe('assert_properties', function() {
    var lib = hqImport("hqwebapp/js/assert_properties"),
        object = {
            alpha: 1,
            beta: 2,
            delta: 3,
        };

    it('should fail if required properties are missing', function() {
        try {
            lib.assert(object, ['alpha', 'beta', 'delta', 'gamma'], []);
        } catch (e) {
            assert.equal(e.message, "Required properties missing: gamma");
        }
    });

    it('should fail if extra properties are provided', function() {
        try {
            lib.assert(object, ['alpha', 'beta'], []);
        } catch (e) {
            assert.equal(e.message, "Unexpected properties encountered: delta");
        }
    });

    it('should pass if all required properties and any optional properties are provided', function() {
        assert(lib.assert(object, ['alpha', 'beta', 'delta'], []));
        assert(lib.assert(object, ['alpha', 'beta'], ['delta']));
        assert(lib.assert(object, [], ['alpha', 'beta', 'delta']));
    });
});
