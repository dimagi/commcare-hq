/* globals hqDefine hqImport django */
hqDefine("app_manager/js/releases/app_view_release_manager", function () {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

    hqImport('app_manager/js/app_manager').setPrependedPageTitle(django.gettext("Releases"));

    // Main releases content
    var releasesMainModel = hqImport('app_manager/js/releases/releases').releasesMainModel;
    var o = {
        currentAppVersion: initial_page_data('app_version') || -1,
        recipient_contacts: initial_page_data('sms_contacts'),
        download_modal_id: '#download-zip-modal',
        latestReleasedVersion: initial_page_data('latestReleasedVersion'),
    };
    var el = $('#releases-table');
    if (el.length) {
        var releasesMain = releasesMainModel(o);
        el.koApplyBindings(releasesMain);
        _.defer(function () { releasesMain.goToPage(1); });
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
