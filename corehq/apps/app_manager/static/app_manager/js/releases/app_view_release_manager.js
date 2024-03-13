hqDefine("app_manager/js/releases/app_view_release_manager", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");

    hqImport('app_manager/js/app_manager').setPrependedPageTitle(gettext("Releases"));

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
                        })
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
    var releasesMainModel = hqImport('app_manager/js/releases/releases').releasesMainModel;
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
    var releasesMain = releasesMainModel(o);
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

    // View changes / app diff
    var appDiff = hqImport('app_manager/js/releases/app_diff').init('#app-diff-modal .modal-body');
    $('#recent-changes-btn').on('click', function () {
        appDiff.renderDiff(initialPageData.get('app_id'), initialPageData.get('latest_build_id'));
    });

    // Build profiles
    var $profilesTab = $('#profiles-tab');
    if ($profilesTab.length) {
        var profiles = hqImport('app_manager/js/releases/language_profiles');
        var latestEnabledVersions = initialPageData.get('latest_version_for_build_profiles');
        profiles.setProfileUrl(initialPageData.get('application_profile_url'));
        var profileManagerModel = profiles.profileManager;
        var appLangs = initialPageData.get('langs');
        var appProfiles = initialPageData.get('build_profiles');
        var enablePracticeUsers = initialPageData.get('enable_practice_users');
        var practiceUsers = initialPageData.get('practice_users');
        var profileManager = profileManagerModel(appProfiles, appLangs, enablePracticeUsers, practiceUsers,
            latestEnabledVersions);
        $profilesTab.koApplyBindings(profileManager);
    }

    $(function () {
        if (initialPageData.get('intro_only')) {
            hqImport('app_manager/js/preview_app').forceShowPreview();
        }

        hqImport('analytix/js/kissmetrix').track.event('Visited the Release Manager');
        if (initialPageData.get('confirm')) {
            hqImport('analytix/js/google').track.event('User actions', 'User created login', window.location.pathname);
            hqImport('analytix/js/google').track.event('User actions', 'Forms', 'Name Your First Project');
        }
    });
});
