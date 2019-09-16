hqDefine("translations/js/app_translations", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/widgets",
    "hqwebapp/js/widgets",   // .hqwebapp-select2
], function (
    $,
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
            $appProfileIdSelect = $form.find('.app-profile-id-select');
            if ($appProfileIdSelect.length) {
                $appProfileIdSelect.html('');
                var appsProfiles = initialPageData.get('appsProfiles');
                if(appsProfiles) {
                    var selectedAppId = $(this).val();
                    if (selectedAppId) {
                        $appProfileIdSelect.append(new Option(gettext('Select Profile'), '', true, true));
                        _.each(appsProfiles[selectedAppId], function(profileDetails, profileId) {
                            $appProfileIdSelect.append(
                                new Option(profileDetails.name, profileId, false, false)
                            );
                        });
                    }
                }
                $appProfileIdSelect.trigger('change');
            }
        });
    });
});
