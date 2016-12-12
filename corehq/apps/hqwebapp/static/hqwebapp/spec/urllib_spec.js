/* eslint-env mocha */
/* global $, sinon */

describe('urllib', function() {
    var urllib = hqImport('hqwebapp/js/urllib.js');
    describe('getUrlParameterFromString', function() {
        it('should return null when URL param missing', function() {
            assert.equal(urllib.getUrlParameterFromString('asdf', '?limit=29'), null);
        });

        it('should return correct value when present in URL', function() {
            assert.equal(urllib.getUrlParameterFromString('limit', '?limit=29'), '29');
        });

        it('should return correct value when multiple present in URL', function() {
            assert.equal(urllib.getUrlParameterFromString('limit', '?limit=29&color=red'), '29');
            assert.equal(urllib.getUrlParameterFromString('color', '?limit=29&color=red'), 'red');
        });
    });
});
