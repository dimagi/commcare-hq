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

    describe('registerUrl', function() {
        it('should fetch a static url', function() {
            urllib.registerUrl("case_importer_uploads", "/a/hqsharedtags/importer/history/uploads/");
            assert.equal(urllib.reverse("case_importer_uploads"), "/a/hqsharedtags/importer/history/uploads/");
        });
        it('should interpolate a templated url', function() {
            urllib.registerUrl("case_importer_upload_file_download", "/a/hqsharedtags/importer/history/uploads/---/");
            assert.equal(urllib.reverse("case_importer_upload_file_download", 'asdf-ghjk'), "/a/hqsharedtags/importer/history/uploads/asdf-ghjk/");
        });
        it('should correctly interpolate a templated url with multiple variables', function() {
            urllib.registerUrl("multiple_args", "/a/---/importer/history/uploads/---/");
            assert.equal(urllib.reverse("multiple_args", 'hqsharedtags', 'asdf-ghjk'), "/a/hqsharedtags/importer/history/uploads/asdf-ghjk/");
        });
    });
});
