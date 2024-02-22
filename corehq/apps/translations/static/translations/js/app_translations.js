hqDefine("translations/js/app_translations", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/widgets",
    "hqwebapp/js/bootstrap3/widgets",   // .hqwebapp-select2
], function (
    $,
    _,
    initialPageData,
    appManagerWidgets
) {
    $(function () {
        // Application version select2: pagination, display comment
        $("[name='version']").each(function () {
            var $select = $(this);
            appManagerWidgets.initVersionDropdown($select, {
                url: function () {
                    var $form = $select.closest("form"),
                        appId = $form.find("[name='app_id']").val();
                    return initialPageData.reverse("paginate_releases", appId);
                },
                width: '100%',
                idValue: 'version',
                initialValue: initialPageData.get('appVersionSelectInitialValue'),
                onlyShowReleased: initialPageData.get('appVersionOnlyShowReleased'),
            });
        });

        // Clear version when application changes
        $("[name='app_id']").change(function () {
            var $form = $(this).closest("form");
            $form.find("[name='version']").val('').trigger('change');
            // update app profile options if present
            var $appBuildProfileIdSelect = $form.find('.app-build-profile-id-select');
            if ($appBuildProfileIdSelect.length) {
                $appBuildProfileIdSelect.html('');
                var buildProfilesPerApp = initialPageData.get('buildProfilesPerApp');
                if (buildProfilesPerApp) {
                    var selectedAppId = $(this).val();
                    if (selectedAppId) {
                        $appBuildProfileIdSelect.append(new Option(gettext('Select Profile'), '', true, true));
                        _.each(buildProfilesPerApp[selectedAppId], function (profileDetails, profileId) {
                            $appBuildProfileIdSelect.append(
                                new Option(profileDetails.name, profileId, false, false)
                            );
                        });
                    }
                }
                $appBuildProfileIdSelect.trigger('change');
            }
        });
    });
});
