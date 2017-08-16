/* globals hqDefine hqImport django */
hqDefine("app_manager/js/releases/app_view_release_manager.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    
    hqImport('app_manager/js/app_manager.js').setPrependedPageTitle(django.gettext("Publish"));

    // Main releases content
    var ReleasesMain = hqImport('app_manager/js/releases/releases.js').ReleasesMain;
    var o = {
        currentAppVersion: initial_page_data('app_version') || -1,
        recipient_contacts: initial_page_data('sms_contacts'),
        download_modal_id: '#download-zip-modal',
        fetchLimit: initial_page_data('fetch_limit'),
    };
    var el = $('#releases-table');
    if (el.length) {
        var releasesMain = new ReleasesMain(o);
        _.defer(function(){ releasesMain.getMoreSavedApps(false); });
        el.koApplyBindings(releasesMain);
    }

    // View changes / app diff
    var appDiff = hqImport('app_manager/js/releases/app_diff.js').init('#app-diff-modal .modal-body');
    $('#recent-changes-btn').on('click', function () {
        appDiff.renderDiff(initial_page_data('app_id'), initial_page_data('latest_build_id'));
    });

    // Build profiles
    var $profilesTab = $('#profiles-tab');
    if ($profilesTab.length) {
        var profiles = hqImport('app_manager/js/releases/language_profiles.js');
        profiles.setProfileUrl(initial_page_data('application_profile_url'));
        var ProfileManager = profiles.ProfileManager;
        var app_langs = initial_page_data("langs");
        var app_profiles = initial_page_data('build_profiles');
        var enable_practice_users = initial_page_data('enable_practice_users');
        var practice_users = initial_page_data('practice_users');
        var profileManager = new ProfileManager(app_profiles, app_langs, enable_practice_users, practice_users);
        $profilesTab.koApplyBindings(profileManager);
    }

    if (initial_page_data('intro_only')) {
        hqImport('app_manager/js/preview_app.js').forceShowPreview();
    }

    $(function() {
        analytics.workflow('Visited the Release Manager');
        if (initial_page_data('confirm')) {
            analytics.usage('User actions', 'User created login', window.location.pathname);
        }
    });
});
