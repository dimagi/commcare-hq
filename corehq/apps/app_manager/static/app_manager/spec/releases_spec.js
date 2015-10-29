/* global $, sinon */

describe('App Releases', function() {
    describe('SavedApp', function() {
        var releases = null,
            urls = {
                download_zip: 'download_zip_url',
                download_multimedia: 'download_multimedia_url',
                fetch: 'fetch_url',
                odk_media: 'odk_media'
            },
            options = {
                urls: urls,
                currentAppVersion: -1,
                recipient_contacts: [],
                download_modal_id: '#download-zip-modal-test'
            },
            ajax_stub;

        beforeEach(function() {
            ajax_stub = sinon.stub($, 'ajax');
            releases = new ReleasesMain(options);
            releases.addSavedApps(get_saved_apps(releases.fetchLimit));
        });

        afterEach(function() {
            ajax_stub.restore();
        });

        function get_saved_apps(num) {
            return _.map(_.range(num), function (version) {
                return {
                    id: version,
                    version: version,
                    doc_type: 'Application',
                    build_comment: '',
                    build_broken: false,
                    is_released: false
                }
            });
        }

        it('should only make one request when downloading zip', function() {
            app = releases.savedApps()[0];
            app.download_application_zip();
            assert.equal($.ajax.callCount, 1);
        });

        it('should use the correct URL for downloading ccz', function() {
            app = releases.savedApps()[0];
            app.download_application_zip();
            assert.equal($.ajax.callCount, 1);
            assert.equal(ajax_stub.firstCall.args[0].url, urls['download_zip']);
        });

        it('should use the correct URL for downloading multimedia', function() {
            app = releases.savedApps()[0];
            app.download_application_zip(true);
            assert.equal($.ajax.callCount, 1);
            assert.equal(ajax_stub.firstCall.args[0].url, urls['download_multimedia']);
        });
    });
});
