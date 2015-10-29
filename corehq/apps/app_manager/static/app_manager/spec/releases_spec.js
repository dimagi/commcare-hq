/* global $, sinon */

describe('App Releases', function() {
    describe('SavedApp', function() {
        var releases = null,
            urls = {
                download_zip: 'download_zip_url',
                fetch: 'fetch_url',
                odk_media: 'odk_media'
            },
            options = {
                urls: urls,
                currentAppVersion: -1,
                recipient_contacts: [],
                download_modal_id: '#download-zip-modal-test'
            },
            ajax_stub,
            clock;

        before(function() {
            clock = sinon.useFakeTimers();
        });

        after(function() {
           clock.restore();
        });

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

    });
});
