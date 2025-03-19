hqDefine("app_manager/js/releases/app_view_release_manager", [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/app_manager",
    "app_manager/js/releases/releases",
    "app_manager/js/releases/language_profiles",
    "app_manager/js/preview_app",
    "analytix/js/kissmetrix",
    "analytix/js/google",
    "app_manager/js/apps_base",
    "app_manager/js/releases/update_prompt",
    "hqwebapp/js/bootstrap3/widgets",
    "commcarehq",
], function (
    $,
    ko,
    _,
    initialPageData,
    appManager,
    releases,
    languageProfiles,
    previewApp,
    kissmetrix,
    google,
) {
    appManager.setPrependedPageTitle(gettext("Releases"));

    var appReleaseLogsModel = function () {
        let self = {};
        self.releaseLogs = ko.observableArray();
        self.fetchLimit = ko.observable();
        self.totalItems = ko.observable();
        self.fetchState = ko.observable();

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        self.goToPage = function (page) {
            if (self.fetchState() === 'pending') {
                return false;
            }
            self.fetchState('pending');
            var url = initialPageData.reverse("paginate_release_logs");
            $.ajax({
                url: url,
                dataType: 'json',
                data: {
                    page: page,
                    limit: self.fetchLimit,
                },
                success: function (data) {
                    self.releaseLogs(
                        _.map(data.app_release_logs, function (log) {
                            return ko.mapping.fromJS(log);
                        }),
                    );
                    self.totalItems(data.pagination.total);
                    self.fetchState('');
                },
                error: function () {
                    self.fetchState('error');
                },
            });
        };

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
        return self;
    };

    var $releaseLogsTab = $('#release-logs-tab');
    var appReleaseLogs = appReleaseLogsModel();
    if ($releaseLogsTab.length) {
        $releaseLogsTab.koApplyBindings(appReleaseLogs);
    }

    // Main releases content
    var o = {
        currentAppVersion: initialPageData.get('app_version') || -1,
        recipient_contacts: initialPageData.get('sms_contacts'),
        download_modal_id: '#download-zip-modal',
        latestReleasedVersion: initialPageData.get('latestReleasedVersion'),
        upstreamBriefs: initialPageData.get('upstream_briefs'),
        upstreamUrl: initialPageData.get('upstream_url'),
        appReleaseLogs: appReleaseLogs,
    };
    var el = $('#releases-table');
    var releasesMain = releases.releasesMainModel(o);
    if (el.length) {
        el.koApplyBindings(releasesMain);
        _.defer(function () { releasesMain.goToPage(1); });

        var releaseControlEl = $('#release-control');
        if (releaseControlEl.length) {
            releasesMain.showReleaseOperations(false);
            var setReleaseLockButtons = function () {
                if (releasesMain.showReleaseOperations()) {
                    $("#btn-release-unlocked").show();
                    $("#btn-release-locked").hide();
                } else {
                    $("#btn-release-unlocked").hide();
                    $("#btn-release-locked").show();
                }
            };

            $("#btn-release-unlocked").click(function () {
                releasesMain.showReleaseOperations(false);
                setReleaseLockButtons();
            });
            $("#btn-release-locked").click(function () {
                releasesMain.showReleaseOperations(true);
                setReleaseLockButtons();
            });

            setReleaseLockButtons();
        }
    }

    // Build profiles
    var $profilesTab = $('#profiles-tab');
    if ($profilesTab.length) {
        var latestEnabledVersions = initialPageData.get('latest_version_for_build_profiles');
        languageProfiles.setProfileUrl(initialPageData.get('application_profile_url'));
        var appLangs = initialPageData.get('langs');
        var appProfiles = initialPageData.get('build_profiles');
        var enablePracticeUsers = initialPageData.get('enable_practice_users');
        var practiceUsers = initialPageData.get('practice_users');
        var profileManager = languageProfiles.profileManager(appProfiles, appLangs, enablePracticeUsers, practiceUsers,
            latestEnabledVersions);
        $profilesTab.koApplyBindings(profileManager);
    }

    $(function () {
        if (initialPageData.get('intro_only')) {
            previewApp.forceShowPreview();
        }

        kissmetrix.track.event('Visited the Release Manager');
        if (initialPageData.get('confirm')) {
            google.track.event('User actions', 'User created login', window.location.pathname);
            google.track.event('User actions', 'Forms', 'Name Your First Project');
        }
    });
});
