/* globals: ga_track_event */
hqDefine('app_manager/js/releases.js', function () {
    function SavedApp(app_data, releasesMain) {
        var self = ko.mapping.fromJS(app_data);
        $.each(['comment_user_name', '_deleteState'], function (i, attr) {
            self[attr] = self[attr] || ko.observable();
        });
        if (!self.include_media) {
            self.include_media = ko.observable(self.doc_type() !== "RemoteApp");
        }
        if(!self.generating_url){
            self.generating_url = ko.observable(false);
        }
        self.include_media.subscribe(function() {
            // If we've generated an app code ensure that we update it when we toggle media
            if (self.app_code()) {
                self.get_app_code();
            }
        });
        self.num_errors = ko.observable(app_data.num_errors || 0);
        self.app_code = ko.observable(null);
        self.failed_url_generation = ko.observable(false);
        self.build_profile = ko.observable('');
        self.base_url = function() {
            return '/a/' + self.domain() + '/apps/odk/' + self.id() + '/';
        };
        self.build_profiles = function() {
            var profiles = [{'label': gettext('(Default)'), 'value': ''}];
            _.each(app_data.build_profiles, function(value, key) {
                profiles.push({'label': value['name'], 'value': key});
            });
            return profiles;
        };

        self.track_deploy_type = function(type) {
            ga_track_event('App Manager', 'Deploy Type', type);
        };

        self.changeAppCode = function () {
            self.app_code(null);
            self.failed_url_generation(false);
            self.generating_url(false);
        };

        self.onSMSPanelClick = function() {
            self.track_deploy_type('Send to phone via SMS');
            self.generate_short_url('short_url');
        };

        self.build_profile.subscribe(self.changeAppCode);

        self.should_generate_url = function(url_type) {
            var types = _.values(SavedApp.URL_TYPES);
            return (types.indexOf(url_type) !== 1 &&
                !ko.utils.unwrapObservable(self[url_type]));
        };

        self.generate_short_url = function(url_type) {
            //accepted_url_types = ['short_odk_url', 'short_odk_media_url', 'short_url']
            url_type = url_type || SavedApp.URL_TYPES.SHORT_ODK_URL;
            var base_url = self.base_url(),
                should_generate_url = self.should_generate_url();

            if (should_generate_url && !self.generating_url()){
                self.generating_url(true);
                $.ajax({
                    url: base_url + url_type + '/?profile=' + self.build_profile(),
                }).done(function(data){
                    var bitly_code = self.parse_bitly_url(data);
                    if (!self.build_profile()) {
                        self[url_type](data);
                    }

                    self.failed_url_generation(!bitly_code);
                    self.app_code(bitly_code);

                }).fail(function() {
                    self.app_code(null);
                    self.failed_url_generation(true);
                }).always(function(){
                    self.generating_url(false);
                });
            }
        };

        self.get_short_odk_url = function() {
            var url_type;
            if (self.include_media()) {
                url_type = SavedApp.URL_TYPES.SHORT_ODK_MEDIA_URL;
            } else {
                url_type = SavedApp.URL_TYPES.SHORT_ODK_URL;
            }
            if (!(ko.utils.unwrapObservable(self[url_type])) || self.build_profile()) {
                return self.generate_short_url(url_type);
            } else {
                return ko.utils.unwrapObservable(self[url_type]);
            }
        };

        self.parse_bitly_url = function(url) {
            // Matches "foo" in "http://bit.ly/foo" and "https://is.gd/X/foo/" ("*" is not greedy)
            var re = /^http.*\/(\w+)\/?/;
            var match = url.match(re);
            if (match) {
                return match[1];
            }
            return null;
        };

        self.click_app_code = function() {
            self.get_app_code();
            ga_track_event('App Manager', 'Initiate Install', 'Get App Code');
            analytics.workflow('Initiate Installation Method');
        };
        
        self.get_app_code = function() {
            var short_odk_url = self.get_short_odk_url();
            if (short_odk_url) {
                self.app_code(self.parse_bitly_url(short_odk_url));
            }
        };

        self.allow_media_install = ko.computed(function(){
            return self.doc_type() !== "RemoteApp";  // remote apps don't support multimedia
        });

        self.mm_supported = function() {
            // This is added to fix legacy issues with incorrectly formatted media_profile.ccpr files.
            // Files that were generated prior to 10/16/2013 are affected, so don't support remote mm for build made before then.
            var supported_date = new Date(2013, 9, 16);
            var date_built = new Date(self.built_on());
            return date_built.getTime() > supported_date.getTime();
        };

        self.get_odk_install_url = ko.computed(function() {
            var slug = self.include_media() ? 'odk_media' : 'odk';
            return releasesMain.url(slug, self.id());
        });

        self.full_odk_install_url = ko.computed(function() {
            return self.get_odk_install_url() + '?profile=' + self.build_profile();
        });

        self.sms_url = function(index) {
            if (index === 0) { // sending to sms
                return self.short_url();
            } else { // sending to odk
                if (self.include_media() && self.short_odk_media_url()) {
                    return self.short_odk_media_url();
                } else {
                    return self.short_odk_url();
                }
            }
        };
        
        self.download_application_zip = function (multimedia_only, build_profile) {
            releasesMain.download_application_zip(self.id(), multimedia_only, build_profile);
        };

        self.clickDeploy = function () {
            ga_track_event('App Manager', 'Deploy Button', self.id());
            analytics.workflow('Clicked Deploy');
            $.post(releasesMain.options.urls.hubspot_click_deploy);
        };

        self.clickScan = function() {
            self.handleScanModal();
            self.trackScan();
        };

        self.handleScanModal = function() {

            // Hide the main deploy modal, then re-open
            // it when the scan barcode modal is closed
            var $deployModal = $('.modal.fade.in');
            $deployModal.modal('hide');
            $('body').one("hide.bs.modal", function() {
                $deployModal.modal({ show: true });
            });
        };

        self.trackScan = function() {
            ga_track_event('App Manager', 'Initiate Install', 'Show Bar Code');
            analytics.workflow('Initiate Installation Method');
        };

        self.reveal_java_download = function(){
            return this.j2me_enabled();
        };
        return self;
    }

    function ReleasesMain(o) {
        /* {fetchUrl, deleteUrl} */
        var AsyncDownloader = hqImport('app_manager/js/download_async_modal.js').AsyncDownloader;
        var self = this;
        self.options = o;
        self.recipients = self.options.recipient_contacts;
        self.savedApps = ko.observableArray();
        self.doneFetching = ko.observable(false);
        self.buildState = ko.observable('');
        self.fetchState = ko.observable('');
        self.nextVersionToFetch = null;
        self.fetchLimit = o.fetchLimit || 5;
        self.deployAnyway = {};
        self.currentAppVersion = ko.observable(self.options.currentAppVersion);
        self.lastAppVersion = ko.observable();
        self.selectingVersion = ko.observable("");

        self.download_modal = $(self.options.download_modal_id);
        self.async_downloader = new AsyncDownloader(self.download_modal);

        self.download_application_zip = function(appId, multimedia_only, build_profile) {
            var url_slug = multimedia_only ? 'download_multimedia' : 'download_zip';
            var url = self.url(url_slug, appId);
            var params = {};
            params.message = "Your application download is ready";
            if (build_profile) {
                params.profile = build_profile;
            }
            self.async_downloader.generateDownload(url, params);
            // Not so nice... Hide the open modal so we don't get bootstrap recursion errors
            // http://stackoverflow.com/questions/13649459/twitter-bootstrap-multiple-modal-error
            $('.modal.fade.in').modal('hide');
            self.download_modal.modal({show: true});
        };

        self.buildButtonEnabled = ko.computed(function () {
            if (self.buildState() === 'pending' || self.fetchState() === 'pending') {
                return false;
            } else {
                return true;
            }
        });
        self.brokenBuilds = ko.computed(function () {
            var apps = self.savedApps();
            return _.some(apps, function (app) {
                return app.build_broken();
            });
        });
        self.savedApps.subscribe(function () {
            var lastApp = self.savedApps()[0];
            self.lastAppVersion(lastApp ? lastApp.version() : -1);
        });
        self.url = function (name) {
            var template = self.options.urls[name];
            for (var i = 1; i < arguments.length; i++) {
                template = template.replace('___', ko.utils.unwrapObservable(arguments[i]));
            }
            return template;
        };
        self.latestReleaseId = ko.computed(function () {
            for (var i = 0; i < self.savedApps().length; i++) {
                var savedApp = self.savedApps()[i];
                if (savedApp.is_released()) {
                    return savedApp.id();
                }
            }
        });

        self.addSavedApp = function (savedApp, toBeginning) {
            if (toBeginning) {
                self.savedApps.unshift(savedApp);
            } else {
                self.savedApps.push(savedApp);
            }
            self.deployAnyway[savedApp.id()] = ko.observable(false);
        };

        self.addSavedApps = function (savedApps) {
            var i, savedApp;
            for (i = 0; i < savedApps.length; i++) {
                savedApp = SavedApp(savedApps[i], self);
                self.addSavedApp(savedApp);
            }
            if (i) {
                self.nextVersionToFetch = savedApps[i - 1].version - 1;
            }
            if (savedApps.length < self.fetchLimit) {
                self.doneFetching(true);
            } else {
                self.doneFetching(false);
            }
        };

        self.getMoreSavedApps = function (scroll) {
            self.fetchState('pending');
            $.ajax({
                url: self.url('fetch'),
                dataType: 'json',
                data: {
                    start_build: self.nextVersionToFetch,
                    limit: self.fetchLimit
                },
                success: function (savedApps) {
                    self.addSavedApps(savedApps);
                    self.fetchState('');
                    if (scroll) {
                        // Scroll so the bottom of main content (and the "View More" button) aligns with the bottom of the window
                        var $content = $("#hq-content");
                        window.scrollTo(0, $content.position().top + $content.height() - window.innerHeight);
                    }
                },
                error: function () {
                    self.fetchState('error');
                }
            });
        };

        self.toggleRelease = function (savedApp) {
            var is_released = savedApp.is_released();
            var saved_app_id = savedApp.id();
            if (savedApp.is_released() !== 'pending') {
                var url = self.url('release', saved_app_id);
                var that = this;
                $.ajax({
                    url: url,
                    type: 'post',
                    dataType: 'json',
                    data: {ajax: true, is_released: !is_released},
                    beforeSend: function (jqXHR, settings) {
                        savedApp.is_released('pending');
                        if ($.ajaxSettings.beforeSend) {
                            $.ajaxSettings.beforeSend(jqXHR, settings);
                        }
                    },
                    success: function (data) {
                        savedApp.is_released(data.is_released);
                    },
                    error: function () {
                        savedApp.is_released('error');
                    }
                });
            }
        };
        self.reload_message = gettext("Sorry, that didn't go through. " +
                "Please reload your page and try again");
        self.deleteSavedApp = function (savedApp) {
            savedApp._deleteState('pending');
            $.post({
                url: self.url('delete'),
                data: {saved_app: savedApp.id()},
                success: function () {
                    self.savedApps.remove(savedApp);
                    savedApp._deleteState(false);
                },
                error: function () {
                    savedApp._deleteState('error');
                    alert(self.reload_message);
                },
            });
        };
        self.revertSavedApp = function (savedApp) {
            $.postGo(self.url('revertBuild'), {saved_app: savedApp.id()});
        };
        self.makeNewBuild = function () {
            if (self.buildState() === 'pending') {
                return false;
            }

            var url = self.url('currentVersion');
            self.fetchState('pending');
            $.get({
                url: self.url('currentVersion'),
                success: function(data) {
                    self.fetchState('');
                    self.currentAppVersion(data.currentVersion);
                    if (!data.latestRelease) {
                        self.actuallyMakeBuild();
                    } else if (data.latestRelease !== self.lastAppVersion()) {
                        window.alert(gettext("The versions list has changed since you loaded the page."));
                        self.reloadApps();
                    } else if (self.lastAppVersion() !== self.currentAppVersion()) {
                        self.actuallyMakeBuild();
                    } else {
                        window.alert(gettext("No new changes to deploy!"));
                    }
                },
                error: function () {
                    self.fetchState('error');
                    window.alert(self.reload_message);
                },
            });
        };
        self.reloadApps = function () {
            self.savedApps([]);
            self.nextVersionToFetch = null;
            self.getMoreSavedApps(false);
        };
        self.actuallyMakeBuild = function () {
            self.buildState('pending');
            $.post({
                url: self.url('newBuild'),
                success: function(data) {
                    $('#build-errors-wrapper').html(data.error_html);
                    if (data.saved_app) {
                        var app = SavedApp(data.saved_app, self);
                        self.addSavedApp(app, true);
                    }
                    self.buildState('');
                },
                error: function() {
                    self.buildState('error');
                },
            });
        };
    }

    SavedApp.URL_TYPES = {
        SHORT_ODK_URL: 'short_odk_url',
        SHORT_ODK_MEDIA_URL: 'short_odk_media_url',
        SHORT_URL: 'short_url'
    };

    return {
        ReleasesMain: ReleasesMain,
        SavedApp: SavedApp
    };
});
