hqDefine('app_manager/js/releases/releases', function () {
    function savedAppModel(appData, releasesMain) {
        var self = ko.mapping.fromJS(appData);
        $.each(['comment_user_name', '_deleteState'], function (i, attr) {
            self[attr] = self[attr] || ko.observable();
        });
        if (!self.include_media) {
            self.include_media = ko.observable(self.doc_type() !== "RemoteApp");
        }
        if (!self.generating_url) {
            self.generating_url = ko.observable(false);
        }
        self.include_media.subscribe(function () {
            // If we've generated an app code ensure that we update it when we toggle media
            if (self.app_code()) {
                self.get_app_code();
            }
        });
        self.num_errors = ko.observable(appData.num_errors || 0);
        self.numErrorsText = ko.computed(function () {
            var s = "s";
            if (self.num_errors() === 1) {
                s = "";
            }
            return self.num_errors() + " Error" + s;
        });
        self.app_code = ko.observable(null);
        self.failed_url_generation = ko.observable(false);
        self.build_profile = ko.observable('');

        self.base_url = function () {
            return '/a/' + self.domain() + '/apps/odk/' + self.id() + '/';
        };
        self.build_profiles = function () {
            var profiles = [{'label': gettext('(Default)'), 'value': ''}],
                appProfilesList = _.map(appData.build_profiles, function (profile, key) {
                    return _.extend(profile, {id: key});
                });
            appProfilesList = _.sortBy(appProfilesList, 'name');
            _.each(appProfilesList, function (profile) {
                profiles.push({label: profile.name, value: profile.id});
            });
            return profiles;
        };

        self.upstream_app_name = ko.computed(function () {
            if (self.doc_type() !== "LinkedApplication") {
                return "";
            }
            var brief = releasesMain.upstreamBriefsById[self.upstream_app_id()] || {};
            return brief.name || gettext("Unknown App");
        });

        self.upstream_app_url = ko.computed(function () {
            if (self.doc_type() !== "LinkedApplication") {
                return "";
            }
            if (releasesMain.upstreamUrl && self.upstream_app_id()) {
                return releasesMain.upstreamUrl.replace('---', self.upstream_app_id());
            }
            return '';
        });

        self.track_deploy_type = function (type) {
            hqImport('analytix/js/google').track.event('App Manager', 'Deploy Type', type);
        };

        self.changeAppCode = function () {
            self.app_code(null);
            self.failed_url_generation(false);
            self.generating_url(false);
        };

        self.onSMSPanelClick = function () {
            self.track_deploy_type('Send to phone via SMS');
        };

        self.build_profile.subscribe(self.changeAppCode);

        self.shouldGenerateUrl = function (urlType) {
            var types = _.values(savedAppModel.URL_TYPES);
            return (types.indexOf(urlType) !== 1 &&
                !ko.utils.unwrapObservable(self[urlType]));
        };

        self.generate_short_url = function (urlType) {
            //accepted url types = ['short_odk_url', 'short_odk_media_url']
            urlType = urlType || savedAppModel.URL_TYPES.SHORT_ODK_URL;
            var baseUrl = self.base_url(),
                shouldGenerateUrl = self.shouldGenerateUrl();

            if (shouldGenerateUrl && !self.generating_url()) {
                self.generating_url(true);
                $.ajax({
                    url: baseUrl + urlType + '/?profile=' + self.build_profile(),
                }).done(function (data) {
                    var bitlyCode = self.parse_bitly_url(data);
                    if (!self.build_profile()) {
                        self[urlType](data);
                    }

                    self.failed_url_generation(!bitlyCode);
                    self.app_code(bitlyCode);

                }).fail(function () {
                    self.app_code(null);
                    self.failed_url_generation(true);
                }).always(function () {
                    self.generating_url(false);
                });
            }
        };

        self.get_odk_url_type = function () {
            if (self.include_media()) {
                return savedAppModel.URL_TYPES.SHORT_ODK_MEDIA_URL;
            } else {
                return savedAppModel.URL_TYPES.SHORT_ODK_URL;
            }
        };
        self.short_odk_url_is_available = function () {
            var urlType = self.get_odk_url_type();
            return ko.utils.unwrapObservable(self[urlType]) && !self.build_profile();
        };
        self.get_short_odk_url = function () {
            var urlType = self.get_odk_url_type();
            if (!self.short_odk_url_is_available()) {
                return self.generate_short_url(urlType);
            } else {
                var data = ko.utils.unwrapObservable(self[urlType]);
                var bitlyCode = self.parse_bitly_url(data);
                self.app_code(bitlyCode);
                return data;
            }
        };

        self.parse_bitly_url = function (url) {
            // Matches "foo" in "http://bit.ly/foo" and "https://is.gd/X/foo/" ("*" is not greedy)
            var re = /^http.*\/(\w+)\/?/;
            var match = url.match(re);
            if (match) {
                return match[1];
            }
            return null;
        };

        self.click_app_code = function () {
            self.get_app_code();
            hqImport('analytix/js/google').track.event('App Manager', 'Initiate Install', 'Get App Code');
            hqImport('analytix/js/kissmetrix').track.event('Initiate Installation Method');
        };

        self.get_app_code = function () {
            var shortOdkUrl = self.get_short_odk_url();
            if (shortOdkUrl) {
                self.app_code(self.parse_bitly_url(shortOdkUrl));
            }
        };

        self.allow_media_install = ko.computed(function () {
            return self.doc_type() !== "RemoteApp";  // remote apps don't support multimedia
        });

        self.mm_supported = function () {
            // This is added to fix legacy issues with incorrectly formatted media_profile.ccpr files.
            // Files that were generated prior to 10/16/2013 are affected, so don't support remote mm for build made before then.
            var supportedDate = new Date(2013, 9, 16);
            var dateBuilt = new Date(self.built_on());
            return dateBuilt.getTime() > supportedDate.getTime();
        };

        self.has_commcare_flavor_target = !!self.commcare_flavor();
        self.download_targeted_version = ko.observable(self.has_commcare_flavor_target);

        self.get_odk_install_url = ko.computed(function () {
            var slug = self.include_media() ? 'odk_media_install' : 'odk_install';
            return releasesMain.reverse(slug, self.id());
        });

        self.full_odk_install_url = ko.computed(function () {
            return self.get_odk_install_url() + '?profile=' + self.build_profile()
              + '&download_target_version=' + (self.download_targeted_version() ? 'true' : '');
        });

        self.sms_odk_url = function () {
            if (self.include_media() && self.short_odk_media_url()) {
                return self.short_odk_media_url();
            }
            return self.short_odk_url();
        };

        self.download_application_zip = function (multimediaOnly, buildProfile) {
            releasesMain.download_application_zip(
                self.id(), multimediaOnly, buildProfile, self.download_targeted_version()
            );
        };

        self.clickDeploy = function () {
            hqImport('analytix/js/google').track.event('App Manager', 'Deploy Button', self.id());
            hqImport('analytix/js/kissmetrix').track.event('Clicked Deploy');
            $.post(releasesMain.reverse('hubspot_click_deploy'));
            if (self.short_odk_url_is_available()) {
                self.get_short_odk_url();
            }
        };

        self.clickScan = function () {
            self.handleScanModal();
            self.trackScan();
        };

        self.handleScanModal = function () {

            // Hide the main deploy modal, then re-open
            // it when the scan barcode modal is closed
            var $deployModal = $('.modal.fade.in');
            $deployModal.modal('hide');
            $('body').one("hide.bs.modal", function () {
                $deployModal.modal({ show: true });
            });
        };

        self.trackScan = function () {
            hqImport('analytix/js/google').track.event('App Manager', 'Initiate Install', 'Show Bar Code');
            hqImport('analytix/js/kissmetrix').track.event('Initiate Installation Method');
        };

        return self;
    }

    function releasesMainModel(o) {
        /* {fetchUrl, deleteUrl} */
        var asyncDownloader = hqImport('app_manager/js/download_async_modal').asyncDownloader;
        var appDiff = hqImport('app_manager/js/releases/app_diff').init('#app-diff-modal .modal-body');
        var self = this;
        self.genericErrorMessage = gettext(
            'An error occurred. Reload the page and click Make New Version to try again.');
        self.options = o;
        self.recipients = self.options.recipient_contacts;
        self.totalItems = ko.observable();
        self.savedApps = ko.observableArray();
        self.doneFetching = ko.observable(false);
        self.buildState = ko.observable('');
        self.buildErrorCode = ko.observable('');
        self.errorMessage = ko.observable(self.genericErrorMessage);
        self.onlyShowReleased = ko.observable(false);
        self.fetchState = ko.observable('');
        self.fetchLimit = ko.observable();
        self.currentAppVersion = ko.observable(self.options.currentAppVersion);
        self.latestReleasedVersion = ko.observable(self.options.latestReleasedVersion);
        self.lastAppVersion = ko.observable();
        self.buildComment = ko.observable();
        self.upstreamBriefsById = _.indexBy(self.options.upstreamBriefs, '_id');
        self.upstreamUrl = self.options.upstreamUrl;
        self.showReleaseOperations = ko.observable(true);
        self.depCaseTypes = ko.observableArray();

        self.download_modal = $(self.options.download_modal_id);
        self.async_downloader = asyncDownloader(self.download_modal);
        self.savedApps.subscribe(() => {
            self.options.appReleaseLogs && self.options.appReleaseLogs.goToPage(1);
        });
        // Spinner behavior
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.fetchState.subscribe(function (newValue) {
            if (newValue === 'pending') {
                self.showPaginationSpinner(true);
            } else {
                self.showLoadingSpinner(false);
                self.showPaginationSpinner(false);
            }
        });

        self.download_application_zip = function (appId, multimediaOnly, buildProfile, downloadTargetedVersion) {
            var urlSlug = multimediaOnly ? 'download_multimedia_zip' : 'download_ccz';
            var url = self.reverse(urlSlug, appId);
            var params = {};
            params.message = "Your application download is ready";
            params.download_targeted_version = downloadTargetedVersion;
            if (buildProfile) {
                params.profile = buildProfile;
            }
            self.async_downloader.generateDownload(url, params);
            // Not so nice... Hide the open modal so we don't get bootstrap recursion errors
            // http://stackoverflow.com/questions/13649459/twitter-bootstrap-multiple-modal-error
            $('.modal.fade.in').modal('hide');
            try {
                self.download_modal.modal({show: true});
            } catch (e) {
                // do nothing. this error only shows up in mocha tests when run
                // via grunt rather than the browser due to how the DOM is
                // interpreted. this runs fine in the browser.
            }
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
        self.reverse = function () {
            for (var i = 1; i < arguments.length; i++) {
                arguments[i] = ko.utils.unwrapObservable(arguments[i]);
            }
            return hqImport("hqwebapp/js/initial_page_data").reverse.apply(null, arguments);
        };
        self.webAppsUrl = function (idObservable, copyOf) {
            var url = hqImport("hqwebapp/js/initial_page_data").reverse("formplayer_main"),
                data = {
                    appId: ko.utils.unwrapObservable(idObservable),
                    copyOf: copyOf,
                };

            return url + '#' + encodeURI(JSON.stringify(data));
        };
        self.app_error_url = function (appId, version) {
            return self.reverse('project_report_dispatcher') + '?app=' + appId + '&version_number=' + version;
        };

        self.previousBuildId = function (index) {
            if (self.savedApps()[index + 1]) {
                return self.savedApps()[index + 1].id();
            }
            return null;
        };

        self.compareUnbuiltChangesUrl = ko.computed(function () {
            if (self.savedApps().length) {
                var latestBuild = self.savedApps()[0];
                return self.reverse('app_form_summary_diff', latestBuild.id(), latestBuild.copy_of());
            }
            return '';
        });

        self.trackClick = function (message) {
            hqImport('analytix/js/kissmetrix').track.event(message);
            return true;
        };

        self.onViewChanges = function (appIdOne, appIdTwo) {
            appDiff.renderDiff(appIdOne, appIdTwo);
        };

        self.goToPage = function (page) {
            if (self.fetchState() === 'pending') {
                return false;
            }
            self.fetchState('pending');
            $.ajax({
                url: self.reverse("paginate_releases"),
                dataType: 'json',
                data: {
                    page: page,
                    limit: self.fetchLimit,
                    only_show_released: self.onlyShowReleased(),
                    query: self.buildComment(),
                },
                success: function (data) {
                    self.savedApps(
                        _.map(data.apps, function (app) {
                            return savedAppModel(app, self);
                        })
                    );
                    self.totalItems(data.pagination.total);
                    self.fetchState('');
                    if (data.pagination.total > 0) {
                        $("#release-control").removeClass("hidden");
                    }
                },
                error: function () {
                    self.fetchState('error');
                },
            });
        };

        self.toggleRelease = function (savedApp, event) {
            $(event.currentTarget).parent().prev('.js-release-waiting').removeClass('hide');
            var isReleased = savedApp.is_released();
            var savedAppId = savedApp.id();
            if (savedApp.is_released() !== 'pending') {
                $.ajax({
                    url: self.reverse('release_build', savedAppId),
                    type: 'post',
                    dataType: 'json',
                    data: {ajax: true, is_released: !isReleased},
                    beforeSend: function (jqXHR, settings) {
                        savedApp.is_released('pending');
                        if ($.ajaxSettings.beforeSend) {
                            $.ajaxSettings.beforeSend(jqXHR, settings);
                        }
                    },
                    success: function (data) {
                        if (data.error) {
                            alert(data.error);
                            $(event.currentTarget).parent().prev('.js-release-waiting').addClass('hide');
                            savedApp.is_released(isReleased);
                        } else {
                            savedApp.is_released(data.is_released);
                            self.latestReleasedVersion(data.latest_released_version);
                            $(event.currentTarget).parent().prev('.js-release-waiting').addClass('hide');
                            self.options.appReleaseLogs && self.options.appReleaseLogs.goToPage(1);
                        }
                    },
                    error: function () {
                        savedApp.is_released('error');
                        $(event.currentTarget).parent().prev('.js-release-waiting').addClass('hide');
                    },
                });
            }
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        self.toggleLimitToReleased = function () {
            self.onlyShowReleased(!self.onlyShowReleased());
            self.goToPage(1);
        };

        self.reload_message = gettext("Sorry, that didn't go through. " +
                "Please reload your page and try again");
        self.deleteSavedApp = function (savedApp) {
            savedApp._deleteState('pending');
            $.post({
                url: self.reverse('delete_copy'),
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
            $.postGo(self.reverse('revert_to_copy'), {build_id: savedApp.id()});
        };
        self.handleDeprecatedCaseTypesWarning = function (depCaseTypes) {
            if (depCaseTypes && depCaseTypes.length) {
                self.depCaseTypes(depCaseTypes);
            } else {
                self.depCaseTypes([]);
            }
        };
        self.makeNewBuild = function () {
            if (self.buildState() === 'pending') {
                return false;
            }

            self.fetchState('pending');
            $.get({
                url: self.reverse('current_app_version'),
                success: function (data) {
                    self.fetchState('');
                    self.currentAppVersion(data.currentVersion);
                    if (!data.latestBuild) {
                        self.actuallyMakeBuild();
                    } else if (data.latestBuild !== self.lastAppVersion()) {
                        window.alert(gettext("The versions list has changed since you loaded the page."));
                        self.reloadApps();
                    } else if (self.lastAppVersion() !== self.currentAppVersion()) {
                        self.actuallyMakeBuild();
                    } else {
                        window.alert(gettext("No new changes!"));
                    }
                },
                error: function () {
                    self.fetchState('error');
                    window.alert(self.reload_message);
                },
            });
        };
        self.reloadApps = function () {
            self.goToPage(1);
        };
        self.actuallyMakeBuild = function () {
            self.buildState('pending');
            self.errorMessage(self.genericErrorMessage);
            $.post({
                url: self.reverse('save_copy'),
                success: function (data) {
                    $('#build-errors-wrapper').html(data.error_html);
                    self.handleDeprecatedCaseTypesWarning(data.deprecated_case_types);
                    if (data.saved_app) {
                        var app = savedAppModel(data.saved_app, self);
                        self.savedApps.unshift(app);
                        $("#release-control").removeClass("hidden");
                    }
                    self.buildState('');
                    self.buildErrorCode('');
                    hqImport('app_manager/js/menu').setPublishStatus(false);
                },
                error: function (xhr) {
                    self.buildErrorCode(xhr.status);
                    self.buildState('error');
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        self.errorMessage(xhr.responseJSON.error);
                    }
                },
            });
        };

        return self;
    }

    savedAppModel.URL_TYPES = {
        SHORT_ODK_URL: 'short_odk_url',
        SHORT_ODK_MEDIA_URL: 'short_odk_media_url',
    };

    return {
        releasesMainModel: releasesMainModel,
        savedAppModel: savedAppModel,
    };
});
