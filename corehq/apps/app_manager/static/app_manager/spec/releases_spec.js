/* eslint-env mocha */
import $ from "jquery";
import _ from "underscore";
import sinon from "sinon";

import initialPageData from "hqwebapp/js/initial_page_data";
import releasesModels from "app_manager/js/releases/releases";

import "commcarehq";

describe('App Releases', function () {
    function getSavedApps(num, extraProps, releasesMain) {
        extraProps = extraProps || {};
        var savedAppModel = releasesModels.savedAppModel,
            savedApps = [];
        for (var version = 0; version <= num; version ++) {
            savedApps.push(savedAppModel(
                _.extend({
                    id: version,
                    version: version,
                    doc_type: 'Application',
                    query: '',
                    build_broken: false,
                    is_released: false,
                    domain: 'test-domain',
                    commcare_flavor: null,
                    copy_of: null,
                }, extraProps),
                releasesMain));
        }
        return savedApps;
    }
    var urls = {
            download_zip: 'download_zip_url ___',
            download_multimedia: 'download_multimedia_url ___',
            fetch: 'fetch_url',
            odk_media: 'odk_media',
            odk: 'odk',
        },
        options = {
            urls: urls,
            currentAppVersion: -1,
            recipient_contacts: [],
            download_modal_id: '#download-zip-modal-test',
        };
    describe('SavedApp', function () {
        var releases = null,
            ajaxStub;

        beforeEach(function () {
            initialPageData.registerUrl("current_app_version", "/a/test-domain/apps/---/current_version/");
            initialPageData.registerUrl("odk_install", "/a/test-domain/apps/odk/---/install/");
            initialPageData.registerUrl("odk_media_install", "/a/test-domain/apps/odk/---/media_install/");
            initialPageData.registerUrl("download_ccz", "/a/text-domain/apps/download/---/CommCare.ccz");
            initialPageData.registerUrl("download_multimedia_zip", "/a/test-domain/apps/download/---/multimedia/commcare.zip");
            initialPageData.registerUrl("app_form_summary_diff", "/a/test-domain/apps/compare/---..---");
            ajaxStub = sinon.stub($, 'ajax');
            releases = releasesModels.releasesMainModel(options);
            releases.savedApps(getSavedApps(5, {}, releases));
        });

        afterEach(function () {
            ajaxStub.restore();
        });

        it('should only make one request when downloading zip', function () {
            var app = releases.savedApps()[0];
            app.download_application_zip();
            assert.equal($.ajax.callCount, 1);
        });

        it('should use the correct URL for downloading ccz', function () {
            var app = releases.savedApps()[0];
            app.download_application_zip();
            assert.equal($.ajax.callCount, 1);
            assert.equal(ajaxStub.firstCall.args[0].url, releases.reverse('download_ccz', app.id()));
        });

        it('should use the correct URL for downloading multimedia', function () {
            var app = releases.savedApps()[0];
            app.download_application_zip(true);
            assert.equal($.ajax.callCount, 1);
            assert.equal(ajaxStub.firstCall.args[0].url, releases.reverse('download_multimedia_zip', app.id()));
        });

        it('should use the correct URL for different saved apps', function () {
            _.each(releases.savedApps(), function (app) {
                ajaxStub.reset();
                ajaxStub.onFirstCall(0).yieldsTo("success", {
                    download_id: '123' + app.id(),
                    download_url: 'pollUrl',
                });
                ajaxStub.onSecondCall().yieldsTo("success", 'ready_123' + app.id());

                app.download_application_zip();
                assert.equal($.ajax.callCount, 2);
                assert.equal(ajaxStub.firstCall.args[0].url, releases.reverse('download_ccz', app.id()));
            });
        });

    });

    describe('app_code', function () {
        var savedAppModel = releasesModels.savedAppModel;
        var savedApp,
            releases;
        beforeEach(function () {
            releases = releasesModels.releasesMainModel(options);

            this.server = sinon.fakeServer.create();
            this.server.respondWith(
                "GET",
                new RegExp(savedAppModel.URL_TYPES.SHORT_ODK_MEDIA_URL),
                [200, { "Content-type": "text/html" }, 'http://bit.ly/media/'],
            );
            this.server.respondWith(
                "GET",
                new RegExp(savedAppModel.URL_TYPES.SHORT_ODK_URL),
                [200, { "Content-type": "text/html" }, 'http://bit.ly/nomedia/'],
            );
        });

        it('should correctly load media url', function () {
            var props = { include_media: true };
            props[savedAppModel.URL_TYPES.SHORT_ODK_MEDIA_URL] = null;
            releases.savedApps(getSavedApps(1, props, releases));

            savedApp = releases.savedApps()[0];

            savedApp.get_app_code();

            assert.equal(savedApp.generating_url(), true);

            this.server.respond();

            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'media');
        });

        it('should correctly load non media url', function () {
            var props = { include_media: false };
            props[savedAppModel.URL_TYPES.SHORT_ODK_URL] = null;
            releases.savedApps(getSavedApps(1, props, releases));

            savedApp = releases.savedApps()[0];

            savedApp.get_app_code();

            assert.equal(savedApp.generating_url(), true);

            this.server.respond();

            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'nomedia');
        });

        it('should correctly toggle between media and non media', function () {
            var props = { include_media: false };

            props[savedAppModel.URL_TYPES.SHORT_ODK_URL] = null;
            props[savedAppModel.URL_TYPES.SHORT_ODK_MEDIA_URL] = null;
            releases.savedApps(getSavedApps(1, props, releases));
            savedApp = releases.savedApps()[0];

            savedApp.get_app_code();

            assert.equal(savedApp.generating_url(), true);

            this.server.respond();

            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'nomedia');

            // Toggle to include media
            savedApp.include_media(true);
            assert.equal(savedApp.generating_url(), true);
            this.server.respond();

            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'media');

            // Toggle and ensure no more ajax calls
            savedApp.include_media(false);
            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'nomedia');

            savedApp.include_media(true);
            assert.equal(savedApp.generating_url(), false);
            assert.equal(savedApp.app_code(), 'media');
        });
    });
});
