hqDefine("app_manager/js/releases/app_view_release_manager", function () {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

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
            var url = hqImport("hqwebapp/js/initial_page_data").reverse("paginate_release_logs");
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
        currentAppVersion: initial_page_data('app_version') || -1,
        recipient_contacts: initial_page_data('sms_contacts'),
        download_modal_id: '#download-zip-modal',
        latestReleasedVersion: initial_page_data('latestReleasedVersion'),
        upstreamBriefs: initial_page_data('upstream_briefs'),
        upstreamUrl: initial_page_data('upstream_url'),
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
        appDiff.renderDiff(initial_page_data('app_id'), initial_page_data('latest_build_id'));
    });

    // Build profiles
    var $profilesTab = $('#profiles-tab');
    if ($profilesTab.length) {
        var profiles = hqImport('app_manager/js/releases/language_profiles');
        var latestEnabledVersions = hqImport("hqwebapp/js/initial_page_data").get(
            'latest_version_for_build_profiles');
        profiles.setProfileUrl(initial_page_data('application_profile_url'));
        var profileManagerModel = profiles.profileManager;
        var app_langs = initial_page_data("langs");
        var app_profiles = initial_page_data('build_profiles');
        var enable_practice_users = initial_page_data('enable_practice_users');
        var practice_users = initial_page_data('practice_users');
        var profileManager = profileManagerModel(app_profiles, app_langs, enable_practice_users, practice_users,
            latestEnabledVersions);
        $profilesTab.koApplyBindings(profileManager);
    }

    $(function () {
        if (initial_page_data('intro_only')) {
            hqImport('app_manager/js/preview_app').forceShowPreview();
        }

        hqImport('analytix/js/kissmetrix').track.event('Visited the Release Manager');
        if (initial_page_data('confirm')) {
            hqImport('analytix/js/google').track.event('User actions', 'User created login', window.location.pathname);
            hqImport('analytix/js/google').track.event('User actions', 'Forms', 'Name Your First Project');
        }
    });
});
