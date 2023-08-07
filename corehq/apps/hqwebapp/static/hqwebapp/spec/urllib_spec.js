/* eslint-env mocha */
hqDefine("hqwebapp/spec/urllib_spec", [
    'hqwebapp/js/initial_page_data',
], function (
    urllib
) {
    describe('urllib', function () {
        describe('getUrlParameterFromString', function () {
            it('should return undefined when URL param missing', function () {
                assert.strictEqual(urllib.getUrlParameterFromString('asdf', '?limit=29'), undefined);
            });

            it('should return correct value when present in URL', function () {
                assert.equal(urllib.getUrlParameterFromString('limit', '?limit=29'), '29');
            });

            it('should return correct value when multiple present in URL', function () {
                assert.equal(urllib.getUrlParameterFromString('limit', '?limit=29&color=red'), '29');
                assert.equal(urllib.getUrlParameterFromString('color', '?limit=29&color=red'), 'red');
            });

            it('should return the URL-decoded value', function () {
                assert.equal(urllib.getUrlParameterFromString('json', '?json=[%22hi%22]'), '["hi"]');
            });

            it('should allow & in the value', function () {
                assert.equal(
                    urllib.getUrlParameterFromString('drink', '?drink=gin%20%26%20tonic&food=eggplant%20parm'),
                    'gin & tonic'
                );
            });
        });

        describe('registerUrl', function () {
            it('should fetch a static url', function () {
                urllib.registerUrl("case_importer_uploads", "/a/hqsharedtags/importer/history/uploads/");
                assert.equal(urllib.reverse("case_importer_uploads"), "/a/hqsharedtags/importer/history/uploads/");
            });
            it('should interpolate a templated url', function () {
                urllib.registerUrl("case_importer_upload_file_download", "/a/hqsharedtags/importer/history/uploads/---/");
                assert.equal(urllib.reverse("case_importer_upload_file_download", 'asdf-ghjk'), "/a/hqsharedtags/importer/history/uploads/asdf-ghjk/");
            });
            it('should correctly interpolate a templated url with multiple variables', function () {
                urllib.registerUrl("multiple_args", "/a/---/importer/history/uploads/---/");
                assert.equal(urllib.reverse("multiple_args", 'hqsharedtags', 'asdf-ghjk'), "/a/hqsharedtags/importer/history/uploads/asdf-ghjk/");
            });
        });
    });
});
